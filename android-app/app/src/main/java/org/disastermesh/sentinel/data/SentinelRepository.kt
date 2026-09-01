package org.disastermesh.sentinel.data

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import org.disastermesh.sentinel.domain.AccessPolicy
import org.disastermesh.sentinel.domain.Condition
import org.disastermesh.sentinel.domain.DisasterType
import org.disastermesh.sentinel.domain.GeoPoint
import org.disastermesh.sentinel.domain.Incident
import org.disastermesh.sentinel.domain.IncidentStatus
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.domain.PriorityEngine
import org.disastermesh.sentinel.domain.Quantity
import org.disastermesh.sentinel.domain.Role
import org.disastermesh.sentinel.domain.Sensitivity
import org.disastermesh.sentinel.domain.Urgency
import org.disastermesh.sentinel.domain.VerificationStatus
import org.disastermesh.sentinel.sync.GatewayClient
import org.disastermesh.sentinel.transport.Transport
import org.disastermesh.sentinel.transport.TransportEvent
import org.json.JSONArray
import org.json.JSONObject
import java.nio.charset.StandardCharsets
import java.time.Instant
import java.util.UUID

data class SyncSummary(val pushed: Int, val pulled: Int, val isOnline: Boolean)

/**
 * Single source of truth coordinating local Room database, Priority Engine,
 * Gateway HTTP synchronization, and Nearby Mesh transport.
 */
class SentinelRepository(
    private val database: SentinelDatabase,
    val context: Context? = null,
    val gatewayClient: GatewayClient = GatewayClient(),
    val nodeId: String = "node_" + UUID.randomUUID().toString().take(8),
    val role: Role = Role.CITIZEN_REPORTER,
) {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val _isOnline = MutableStateFlow(false)
    val isOnline = _isOnline.asStateFlow()

    private val _nearbyPeersCount = MutableStateFlow(0)
    val nearbyPeersCount = _nearbyPeersCount.asStateFlow()

    private val _relayActive = MutableStateFlow(false)
    val relayActive = _relayActive.asStateFlow()

    private val _batteryPercent = MutableStateFlow(100)
    val batteryPercent = _batteryPercent.asStateFlow()

    private val _storageFreeMb = MutableStateFlow(1024L)
    val storageFreeMb = _storageFreeMb.asStateFlow()

    private val _isCharging = MutableStateFlow(false)
    val isCharging = _isCharging.asStateFlow()

    private var activeTransport: Transport? = null

    val allIncidents: Flow<List<Incident>> = database.incidents().observeQueue().map { list ->
        list.map { it.toDomain() }
    }

    val carriedBundlesCount: Flow<Int> = database.bundles().observeCount()

    init {
        refreshTelemetry()
        // Periodic gateway health & heartbeat probe
        scope.launch {
            while (true) {
                checkConnection()
                kotlinx.coroutines.delay(10_000)
            }
        }
    }

    fun refreshTelemetry() {
        context?.let { ctx ->
            val t = org.disastermesh.sentinel.util.DeviceTelemetry.getTelemetry(ctx)
            _batteryPercent.value = t.batteryPercent
            _storageFreeMb.value = t.storageFreeMb
            _isCharging.value = t.isCharging
        }
    }

    suspend fun checkConnection(): Boolean {
        refreshTelemetry()
        val online = gatewayClient.checkHealth()
        _isOnline.value = online
        if (online) {
            val bundleCount = try { database.incidents().count() } catch (_: Exception) { 0 }
            gatewayClient.heartbeat(
                nodeId = nodeId,
                role = role.name,
                batteryPercent = _batteryPercent.value,
                nearbyPeers = _nearbyPeersCount.value,
                storedBundles = bundleCount,
            )
            // Push queued incidents if any exist
            try {
                val queuedEntities = database.incidents().byStatus(IncidentStatus.QUEUED.name)
                if (queuedEntities.isNotEmpty()) {
                    val pushRes = gatewayClient.pushSync(nodeId, queuedEntities.map { it.toDomain() })
                    if (pushRes.isSuccess) {
                        queuedEntities.forEach { entity ->
                            val updated = entity.copy(status = IncidentStatus.RECEIVED.name, updatedAt = Instant.now().toEpochMilli())
                            database.incidents().upsert(updated)
                        }
                    }
                }
            } catch (_: Exception) {}
        }
        return online
    }

    /**
     * Create a new emergency report.
     * Always scores deterministically via PriorityEngine and commits locally before sending.
     */
    suspend fun createReport(
        text: String,
        disasterTypes: List<DisasterType> = emptyList(),
        urgency: Urgency = Urgency.UNKNOWN,
        severity: Int = 0,
        peopleAffected: Quantity = Quantity.unknown(),
        conditions: List<Condition> = emptyList(),
        location: GeoPoint? = null,
        sharePrecisely: Boolean = true,
    ): Incident {
        val now = Instant.now()
        val incidentId = "inc_" + UUID.randomUUID().toString().take(12)

        val adjustedLoc = if (location != null && !sharePrecisely) location.coarse() else location

        val inputs = PriorityEngine.Inputs(
            urgency = urgency,
            severity = severity,
            disasterTypes = disasterTypes,
            conditions = conditions,
            peopleAffected = peopleAffected,
        )
        val decision = PriorityEngine.evaluate(inputs)

        val incident = Incident(
            id = incidentId,
            sourceNodeId = nodeId,
            originalText = text,
            sourceLanguage = "en",
            location = adjustedLoc,
            reportedAt = now,
            disasterTypes = disasterTypes,
            urgency = urgency,
            severity = severity,
            peopleAffected = peopleAffected,
            conditions = conditions,
            priorityScore = decision.score,
            priorityClass = decision.priorityClass,
            priorityExplanation = decision.explanation,
            status = IncidentStatus.QUEUED,
            verificationStatus = VerificationStatus.AI_CLASSIFIED,
            accessPolicy = AccessPolicy(
                sensitivity = decision.sensitivity,
                allowedRoles = decision.allowedRoles,
            ),
        )

        // 1. Commit to local SQLite / Room
        val entity = incident.toEntity()
        val event = EventLogEntity(
            id = "evt_" + UUID.randomUUID().toString().take(8),
            incidentId = incidentId,
            actorNodeId = nodeId,
            actorRole = role.name,
            action = "INCIDENT_CREATED",
            detail = "Priority ${decision.priorityClass.name} (score ${decision.score})",
            prevHash = null,
            entryHash = UUID.randomUUID().toString(),
            createdAt = now.toEpochMilli(),
        )
        database.applyTransition(entity, event)

        // 2. Build and store wire bundle for mesh relay
        val bundlePayload = incidentToWireJson(incident).toByteArray(StandardCharsets.UTF_8)
        val bundleEntity = BundleEntity(
            bundleId = "bun_" + incidentId,
            incidentId = incidentId,
            payloadType = "INCIDENT_TEXT",
            priorityClass = decision.priorityClass.name,
            priorityScore = decision.score,
            expiresAt = now.plusSeconds(decision.ttlSeconds).toEpochMilli(),
            hopCount = 0,
            wire = bundlePayload,
            receivedFrom = null,
        )
        database.bundles().insert(bundleEntity)

        // 3. Attempt direct Gateway sync if online
        scope.launch {
            if (_isOnline.value) {
                val res = gatewayClient.submitIncident(incident)
                if (res.isSuccess) {
                    val updated = incident.copy(status = IncidentStatus.RECEIVED)
                    database.incidents().upsert(updated.toEntity())
                }
            }
        }

        // 4. If mesh transport is active, broadcast to nearby peers
        activeTransport?.let { transport ->
            broadcastBundle(bundleEntity, transport)
        }

        return incident
    }

    suspend fun acknowledgeIncident(incidentId: String, note: String? = null): Boolean {
        val existing = database.incidents().byId(incidentId) ?: return false
        val now = Instant.now()
        val updated = existing.copy(
            status = IncidentStatus.ACKNOWLEDGED.name,
            updatedAt = now.toEpochMilli(),
        )
        val event = EventLogEntity(
            id = "evt_" + UUID.randomUUID().toString().take(8),
            incidentId = incidentId,
            actorNodeId = nodeId,
            actorRole = role.name,
            action = "INCIDENT_ACKNOWLEDGED",
            detail = note ?: "Coordinator acknowledged",
            prevHash = null,
            entryHash = UUID.randomUUID().toString(),
            createdAt = now.toEpochMilli(),
        )
        database.applyTransition(updated, event)

        scope.launch {
            if (_isOnline.value) {
                gatewayClient.acknowledge(incidentId, nodeId, note)
            }
        }
        return true
    }

    suspend fun dispatchResource(
        incidentId: String,
        resourceId: String,
        reason: String,
    ): Result<String> {
        val existing = database.incidents().byId(incidentId)
        val now = Instant.now()
        if (existing != null) {
            val updated = existing.copy(
                status = IncidentStatus.DISPATCHED.name,
                updatedAt = now.toEpochMilli(),
            )
            val event = EventLogEntity(
                id = "evt_" + UUID.randomUUID().toString().take(8),
                incidentId = incidentId,
                actorNodeId = nodeId,
                actorRole = role.name,
                action = "DISPATCH_AUTHORIZED",
                detail = "Dispatched $resourceId ($reason)",
                prevHash = null,
                entryHash = UUID.randomUUID().toString(),
                createdAt = now.toEpochMilli(),
            )
            database.applyTransition(updated, event)
        }

        return if (_isOnline.value) {
            gatewayClient.dispatch(incidentId, resourceId, reason)
        } else {
            Result.success("dsp_local_" + UUID.randomUUID().toString().take(6))
        }
    }

    suspend fun syncWithGateway(): SyncSummary {
        val online = checkConnection()
        if (!online) return SyncSummary(0, 0, false)

        var pushed = 0
        var pulled = 0

        // 1. Push all queued local incidents
        try {
            val queuedEntities = database.incidents().byStatus(IncidentStatus.QUEUED.name)
            val queuedIncidents = queuedEntities.map { it.toDomain() }
            if (queuedIncidents.isNotEmpty()) {
                val pushRes = gatewayClient.pushSync(nodeId, queuedIncidents)
                if (pushRes.isSuccess) {
                    val (accepted, dedup) = pushRes.getOrDefault(Pair(0, 0))
                    pushed = accepted + dedup
                    queuedEntities.forEach { entity ->
                        val updated = entity.copy(status = IncidentStatus.RECEIVED.name, updatedAt = Instant.now().toEpochMilli())
                        database.incidents().upsert(updated)
                    }
                }
            }
        } catch (_: Exception) {}

        // 2. Pull remote incidents from Gateway
        try {
            val remote = gatewayClient.pullSync()
            if (remote.isSuccess) {
                val items = remote.getOrNull() ?: emptyList()
                items.forEach { database.incidents().upsertIfNewer(it.toEntity()) }
                pulled = items.size
            }
        } catch (_: Exception) {}

        return SyncSummary(pushed, pulled, true)
    }

    fun attachTransport(transport: Transport) {
        activeTransport = transport
        _relayActive.value = true
        transport.startAdvertising(mapOf("role" to role.name))
        transport.startDiscovery()

        scope.launch {
            transport.events.collect { event ->
                when (event) {
                    is TransportEvent.PeerDiscovered -> {
                        _nearbyPeersCount.value = _nearbyPeersCount.value + 1
                        transport.requestConnection(event.peer.endpointId)
                    }
                    is TransportEvent.PeerLost -> {
                        _nearbyPeersCount.value = maxOf(0, _nearbyPeersCount.value - 1)
                    }
                    is TransportEvent.Connected -> {
                        // Push carried bundles to new peer
                        syncBundlesWithPeer(event.peer.endpointId, transport)
                    }
                    is TransportEvent.PayloadReceived -> {
                        if (event.bytes != null) {
                            handleIncomingWirePayload(event.bytes, event.peer.nodeId)
                        }
                    }
                    else -> {}
                }
            }
        }
    }

    fun detachTransport() {
        activeTransport?.stopAdvertising()
        activeTransport?.stopDiscovery()
        activeTransport = null
        _relayActive.value = false
        _nearbyPeersCount.value = 0
    }

    private suspend fun syncBundlesWithPeer(endpointId: String, transport: Transport) {
        val allIds = database.bundles().allIds()
        for (id in allIds) {
            val bundle = database.bundles().byId(id) ?: continue
            try {
                transport.sendBytes(endpointId, bundle.wire)
            } catch (_: Exception) {}
        }
    }

    private fun broadcastBundle(bundle: BundleEntity, transport: Transport) {
        // Will be delivered when connected endpoints exist
    }

    private suspend fun handleIncomingWirePayload(bytes: ByteArray, senderNodeId: String) {
        try {
            val jsonStr = String(bytes, StandardCharsets.UTF_8)
            val json = JSONObject(jsonStr)
            val incident = jsonToIncident(json) ?: return

            val bundleId = "bun_" + incident.id
            if (!database.bundles().exists(bundleId)) {
                val bundleEntity = BundleEntity(
                    bundleId = bundleId,
                    incidentId = incident.id,
                    payloadType = "INCIDENT_TEXT",
                    priorityClass = incident.priorityClass.name,
                    priorityScore = incident.priorityScore,
                    expiresAt = Instant.now().plusSeconds(86400).toEpochMilli(),
                    hopCount = json.optInt("hop_count", 0) + 1,
                    wire = bytes,
                    receivedFrom = senderNodeId,
                )
                database.bundles().insert(bundleEntity)
                database.incidents().upsertIfNewer(incident.toEntity())
            }
        } catch (_: Exception) {}
    }

    companion object {
        fun Incident.toEntity(): IncidentEntity {
            return IncidentEntity(
                id = id,
                sourceNodeId = sourceNodeId,
                organizationId = organizationId,
                originalText = originalText,
                sourceLanguage = sourceLanguage,
                status = status.name,
                priorityClass = priorityClass.name,
                priorityScore = priorityScore,
                severity = severity,
                urgency = urgency.name,
                sensitivity = accessPolicy.sensitivity.name,
                verificationStatus = verificationStatus.name,
                expiresAt = expiresAt?.toEpochMilli(),
                reportedAt = reportedAt.toEpochMilli(),
                revision = revision,
                doc = incidentToWireJson(this),
                updatedAt = updatedAt.toEpochMilli(),
            )
        }

        fun IncidentEntity.toDomain(): Incident {
            val docJson = try { JSONObject(doc) } catch (_: Exception) { JSONObject() }
            val types = mutableListOf<DisasterType>()
            val typesArr = docJson.optJSONArray("disaster_types")
            if (typesArr != null) {
                for (i in 0 until typesArr.length()) {
                    try { types.add(DisasterType.valueOf(typesArr.getString(i))) } catch (_: Exception) {}
                }
            }

            val locObj = docJson.optJSONObject("location")
            val location = locObj?.let {
                GeoPoint(
                    latitude = it.optDouble("latitude", 0.0),
                    longitude = it.optDouble("longitude", 0.0),
                    accuracyMeters = it.optDouble("accuracy_m", 10.0),
                    sharedPrecisely = it.optBoolean("shared_precisely", true),
                )
            }

            val pObj = docJson.optJSONObject("people_affected")
            val pVal = pObj?.optInt("value", -1)?.takeIf { it >= 0 }
            val pRaw = pObj?.optString("raw", null)

            val explanationList = mutableListOf<String>()
            val expArr = docJson.optJSONArray("priority_explanation")
            if (expArr != null) {
                for (i in 0 until expArr.length()) {
                    explanationList.add(expArr.getString(i))
                }
            }

            return Incident(
                id = id,
                sourceNodeId = sourceNodeId,
                originalText = originalText,
                sourceLanguage = sourceLanguage,
                organizationId = organizationId,
                location = location,
                reportedAt = Instant.ofEpochMilli(reportedAt),
                expiresAt = expiresAt?.let { Instant.ofEpochMilli(it) },
                disasterTypes = types,
                urgency = try { Urgency.valueOf(urgency) } catch (_: Exception) { Urgency.UNKNOWN },
                severity = severity,
                peopleAffected = Quantity(value = pVal, raw = pRaw),
                priorityScore = priorityScore,
                priorityClass = try { PriorityClass.valueOf(priorityClass) } catch (_: Exception) { PriorityClass.P3 },
                priorityExplanation = explanationList,
                status = try { IncidentStatus.valueOf(status) } catch (_: Exception) { IncidentStatus.QUEUED },
                verificationStatus = try { VerificationStatus.valueOf(verificationStatus) } catch (_: Exception) { VerificationStatus.UNVERIFIED },
                accessPolicy = AccessPolicy(
                    sensitivity = try { Sensitivity.valueOf(sensitivity) } catch (_: Exception) { Sensitivity.OPERATIONAL }
                ),
                revision = revision,
                updatedAt = Instant.ofEpochMilli(updatedAt),
            )
        }

        fun incidentToWireJson(incident: Incident): String {
            val obj = JSONObject().apply {
                put("id", incident.id)
                put("source_node_id", incident.sourceNodeId)
                put("original_text", incident.originalText)
                put("source_language", incident.sourceLanguage)
                put("urgency", incident.urgency.name)
                put("severity", incident.severity)
                put("priority_class", incident.priorityClass.name)
                put("priority_score", incident.priorityScore)
                put("status", incident.status.name)
                put("revision", incident.revision)
                put("reported_at", incident.reportedAt.toString())

                val types = JSONArray()
                incident.disasterTypes.forEach { types.put(it.name) }
                put("disaster_types", types)

                incident.location?.let {
                    put("location", JSONObject().apply {
                        put("latitude", it.latitude)
                        put("longitude", it.longitude)
                        put("accuracy_m", it.accuracyMeters ?: 10.0)
                        put("shared_precisely", it.sharedPrecisely)
                    })
                }

                put("people_affected", JSONObject().apply {
                    put("value", incident.peopleAffected.value ?: JSONObject.NULL)
                    put("raw", incident.peopleAffected.raw ?: JSONObject.NULL)
                })

                val exp = JSONArray()
                incident.priorityExplanation.forEach { exp.put(it) }
                put("priority_explanation", exp)
            }
            return obj.toString()
        }

        private fun jsonToIncident(json: JSONObject): Incident? {
            val id = json.optString("id")
            val text = json.optString("original_text")
            if (id.isBlank() || text.isBlank()) return null

            val pClass = try {
                PriorityClass.valueOf(json.optString("priority_class", "P3"))
            } catch (_: Exception) {
                PriorityClass.P3
            }

            return Incident(
                id = id,
                sourceNodeId = json.optString("source_node_id", "unknown"),
                originalText = text,
                sourceLanguage = json.optString("source_language", "und"),
                reportedAt = Instant.now(),
                priorityClass = pClass,
                priorityScore = json.optInt("priority_score", 0),
                status = IncidentStatus.QUEUED,
            )
        }
    }
}
