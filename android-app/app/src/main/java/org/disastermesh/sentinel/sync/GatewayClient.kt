package org.disastermesh.sentinel.sync

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.disastermesh.sentinel.domain.DisasterType
import org.disastermesh.sentinel.domain.GeoPoint
import org.disastermesh.sentinel.domain.Incident
import org.disastermesh.sentinel.domain.IncidentStatus
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.domain.Quantity
import org.disastermesh.sentinel.domain.VerificationStatus
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

/**
 * HTTP client communicating with the DisasterMesh Gateway API.
 *
 * Connects mobile nodes to the central coordinator when internet/LAN is available.
 * All methods run on [Dispatchers.IO] and return [Result] so network failures never crash the app.
 */
class GatewayClient(
    var baseUrl: String = DEFAULT_BASE_URL,
    var apiKey: String = DEFAULT_API_KEY,
) {
    // Shared across every WebSocket connection this client opens; okhttp's own
    // pooling/threading makes one long-lived instance the correct lifetime,
    // not one per call like the raw HttpURLConnection methods below.
    private val httpClient = okhttp3.OkHttpClient()

    suspend fun checkHealth(): Boolean = withContext(Dispatchers.IO) {
        val paths = listOf("/health", "/v1/health", "/")
        for (path in paths) {
            try {
                val url = URL("${cleanBaseUrl()}$path")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 4000
                    readTimeout = 4000
                    setRequestProperty("User-Agent", "DisasterMesh-Android")
                    setRequestProperty("Bypass-Tunnel-Reminder", "true")
                    setRequestProperty("ngrok-skip-browser-warning", "true")
                }
                if (conn.responseCode in 200..299) {
                    return@withContext true
                }
            } catch (_: Exception) {
            }
        }
        false
    }

    suspend fun submitIncident(incident: Incident): Result<String> = withContext(Dispatchers.IO) {
        try {
            val url = URL("${cleanBaseUrl()}/v1/incidents")
            val json = incidentToJson(incident)
            val response = postJson(url, json.toString(), apiKey)
            val obj = JSONObject(response)
            Result.success(obj.optString("id", incident.id))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun pushSync(nodeId: String, incidents: List<Incident>): Result<Pair<Int, Int>> =
        withContext(Dispatchers.IO) {
            try {
                val url = URL("${cleanBaseUrl()}/v1/sync/push")
                val json = JSONObject().apply {
                    put("node_id", nodeId)
                    val arr = JSONArray()
                    incidents.forEach { arr.put(incidentToJson(it)) }
                    put("incidents", arr)
                }
                val response = postJson(url, json.toString(), apiKey)
                val obj = JSONObject(response)
                Result.success(Pair(obj.optInt("accepted", 0), obj.optInt("deduplicated", 0)))
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    suspend fun pullSync(): Result<List<Incident>> = withContext(Dispatchers.IO) {
        try {
            val url = URL("${cleanBaseUrl()}/v1/sync/pull")
            val response = getJson(url, apiKey)
            val obj = JSONObject(response)
            val items = obj.optJSONArray("items") ?: JSONArray()
            val list = mutableListOf<Incident>()
            for (i in 0 until items.length()) {
                val item = items.getJSONObject(i)
                jsonToIncident(item)?.let { list.add(it) }
            }
            Result.success(list)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /** A coordinator note as the gateway stores it — mirrors the dashboard's identical shape. */
    data class IncidentNoteDto(
        val id: String,
        val text: String,
        val source: String,
        val audioAttachmentId: String?,
    )

    /**
     * The app has no other reason to fetch the rich `/v1/incidents/{id}`
     * detail response (everything else rides the mesh/Room path) — this pulls
     * just the `notes` array out of it.
     */
    suspend fun getIncidentNotes(incidentId: String): Result<List<IncidentNoteDto>> =
        withContext(Dispatchers.IO) {
            try {
                val url = URL("${cleanBaseUrl()}/v1/incidents/$incidentId")
                val response = getJson(url, apiKey)
                val notesArr = JSONObject(response).optJSONArray("notes") ?: JSONArray()
                val list = mutableListOf<IncidentNoteDto>()
                for (i in 0 until notesArr.length()) {
                    val n = notesArr.getJSONObject(i)
                    list.add(
                        IncidentNoteDto(
                            id = n.optString("id"),
                            text = n.optString("text"),
                            source = n.optString("source", "text"),
                            audioAttachmentId = n.optString("audio_attachment_id").takeIf { it.isNotBlank() },
                        )
                    )
                }
                Result.success(list)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    suspend fun acknowledge(incidentId: String, nodeId: String, note: String?): Result<Boolean> =
        withContext(Dispatchers.IO) {
            try {
                val url = URL("${cleanBaseUrl()}/v1/incidents/$incidentId/acknowledge")
                val json = JSONObject().apply {
                    put("node_id", nodeId)
                    note?.let { put("note", it) }
                }
                val response = postJson(url, json.toString(), apiKey)
                val obj = JSONObject(response)
                Result.success(obj.has("status"))
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    suspend fun dispatch(
        incidentId: String,
        resourceId: String,
        reason: String,
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val url = URL("${cleanBaseUrl()}/v1/dispatch?confirm=true")
            val json = JSONObject().apply {
                put("incident_id", incidentId)
                put("resource_id", resourceId)
                put("reason", reason)
            }
            val response = postJson(url, json.toString(), apiKey)
            val obj = JSONObject(response)
            Result.success(obj.optString("id", ""))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun heartbeat(
        nodeId: String,
        role: String,
        batteryPercent: Int,
        nearbyPeers: Int,
        storedBundles: Int,
    ): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val url = URL("${cleanBaseUrl()}/v1/nodes/heartbeat")
            val json = JSONObject().apply {
                put("node_id", nodeId)
                put("role", role)
                put("battery_percent", batteryPercent)
                put("nearby_peers", nearbyPeers)
                put("stored_bundles", storedBundles)
            }
            postJson(url, json.toString(), apiKey)
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Upload an image's bytes for an incident so the coordinator can see the actual
     * photo. Additive: mirrors the gateway's /attachments endpoint with inline bytes,
     * and leaves the existing text/sync paths untouched.
     */
    suspend fun uploadImageAttachment(
        incidentId: String,
        bytes: ByteArray,
        fileName: String,
        mimeType: String,
    ): Result<String> = uploadAttachment(incidentId, bytes, fileName, mimeType, kind = "IMAGE")

    /**
     * Upload a recorded voice note's raw audio as a real attachment — the
     * provenance copy kept regardless of whether transcription succeeds.
     * MediaRecorder's MPEG-4/AAC output (`audio/mp4`) is already accepted by
     * the gateway's attachment MIME whitelist.
     */
    suspend fun uploadAudioAttachment(
        incidentId: String,
        bytes: ByteArray,
        fileName: String,
        mimeType: String,
    ): Result<String> = uploadAttachment(incidentId, bytes, fileName, mimeType, kind = "AUDIO")

    private suspend fun uploadAttachment(
        incidentId: String,
        bytes: ByteArray,
        fileName: String,
        mimeType: String,
        kind: String,
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val sha256 = java.security.MessageDigest.getInstance("SHA-256")
                .digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val json = JSONObject().apply {
                put("file_name", fileName)
                put("mime_type", mimeType)
                put("size_bytes", bytes.size)
                put("sha256", sha256)
                put("kind", kind)
                put("data_base64", android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP))
            }
            val url = URL("${cleanBaseUrl()}/v1/incidents/$incidentId/attachments")
            val response = postJson(url, json.toString(), apiKey)
            Result.success(JSONObject(response).optString("id"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * A durable, listable follow-up note — typed, or transcribed voice a human
     * reviewed and confirmed first. Mirrors the dashboard's identical endpoint.
     */
    suspend fun addNote(
        incidentId: String,
        text: String,
        source: String,
        audioAttachmentId: String? = null,
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("text", text)
                put("source", source)
                put("audio_attachment_id", audioAttachmentId ?: JSONObject.NULL)
            }
            val url = URL("${cleanBaseUrl()}/v1/incidents/$incidentId/notes")
            val response = postJson(url, json.toString(), apiKey)
            Result.success(JSONObject(response).optString("id"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Realtime push: every message is `{"type": ..., "incident_id": ...}` — a
     * signal to refetch, never a data payload — same scheme the dashboard's
     * useIncidentSocket.ts already uses against this same endpoint. Returns
     * null if the socket can't even be opened (e.g. malformed base URL); the
     * caller's existing polling loop is the fallback either way.
     */
    fun connectRealtime(onEvent: () -> Unit, onDisconnected: () -> Unit): okhttp3.WebSocket? {
        val wsUrl = cleanBaseUrl().replaceFirst(Regex("^http"), "ws") +
            "/v1/ws/incidents?token=$apiKey"
        return try {
            val request = okhttp3.Request.Builder().url(wsUrl).build()
            httpClient.newWebSocket(request, object : okhttp3.WebSocketListener() {
                override fun onMessage(webSocket: okhttp3.WebSocket, text: String) {
                    onEvent()
                }
                override fun onClosed(webSocket: okhttp3.WebSocket, code: Int, reason: String) {
                    onDisconnected()
                }
                override fun onFailure(
                    webSocket: okhttp3.WebSocket,
                    t: Throwable,
                    response: okhttp3.Response?,
                ) {
                    onDisconnected()
                }
            })
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Turn recorded or selected audio into text using the gateway's speech-to-text
     * endpoint. The caller then sends that text through the ordinary report flow.
     */
    suspend fun transcribeAudio(
        bytes: ByteArray,
        mimeType: String = "audio/ogg",
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("audio_base64", android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP))
                put("mime_type", mimeType)
            }
            val url = URL("${cleanBaseUrl()}/v1/transcribe")
            val response = postJson(url, json.toString(), apiKey)
            Result.success(JSONObject(response).optString("text"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /** URL the coordinator UI loads (with the bearer header) to render an image. */
    fun attachmentContentUrl(incidentId: String, attachmentId: String): String =
        "${cleanBaseUrl()}/v1/incidents/$incidentId/attachments/$attachmentId/content"

    private fun cleanBaseUrl(): String = baseUrl.trim().removeSuffix("/")

    private fun postJson(url: URL, body: String, token: String): String {
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 5000
            readTimeout = 5000
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=UTF-8")
            setRequestProperty("Authorization", "Bearer $token")
            setRequestProperty("User-Agent", "DisasterMesh-Android")
            setRequestProperty("Bypass-Tunnel-Reminder", "true")
            setRequestProperty("ngrok-skip-browser-warning", "true")
        }
        OutputStreamWriter(conn.outputStream, "UTF-8").use { it.write(body); it.flush() }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val response = BufferedReader(InputStreamReader(stream, "UTF-8")).use { it.readText() }
        if (code !in 200..299) {
            throw Exception("HTTP $code: $response")
        }
        return response
    }

    private fun getJson(url: URL, token: String): String {
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 5000
            readTimeout = 5000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Authorization", "Bearer $token")
            setRequestProperty("User-Agent", "DisasterMesh-Android")
            setRequestProperty("Bypass-Tunnel-Reminder", "true")
            setRequestProperty("ngrok-skip-browser-warning", "true")
        }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val response = BufferedReader(InputStreamReader(stream, "UTF-8")).use { it.readText() }
        if (code !in 200..299) {
            throw Exception("HTTP $code: $response")
        }
        return response
    }

    private fun incidentToJson(incident: Incident): JSONObject = JSONObject().apply {
        put("id", incident.id)
        put("source_node_id", incident.sourceNodeId)
        put("original_text", incident.originalText)
        put("source_language", incident.sourceLanguage)
        incident.location?.let {
            put("latitude", it.latitude)
            put("longitude", it.longitude)
            put("location_accuracy_m", it.accuracyMeters ?: 10.0)
        }
        val types = JSONArray()
        incident.disasterTypes.forEach { types.put(it.name) }
        put("disaster_types", types)
        put("urgency", incident.urgency.name)
        put("severity", incident.severity)
        put("priority_class", incident.priorityClass.name)
        put("priority_score", incident.priorityScore)
        put("sensitivity", incident.accessPolicy.sensitivity.name)
        put("revision", incident.revision)
        val exp = JSONArray()
        incident.priorityExplanation.forEach { exp.put(it) }
        put("priority_explanation", exp)
    }

    private fun jsonToIncident(json: JSONObject): Incident? {
        val id = json.optString("id")
        val originalText = json.optString("original_text")
        if (id.isBlank() || originalText.isBlank()) return null

        val priorityClassStr = json.optString("priority_class", "P3")
        val priorityClass = try {
            PriorityClass.valueOf(priorityClassStr)
        } catch (_: Exception) {
            PriorityClass.P3
        }

        val statusStr = json.optString("status", "RECEIVED")
        val status = try {
            IncidentStatus.valueOf(statusStr)
        } catch (_: Exception) {
            IncidentStatus.RECEIVED
        }

        val types = mutableListOf<DisasterType>()
        val typesArr = json.optJSONArray("disaster_types")
        if (typesArr != null) {
            for (i in 0 until typesArr.length()) {
                val t = typesArr.getString(i)
                try {
                    types.add(DisasterType.valueOf(t))
                } catch (_: Exception) {}
            }
        }

        val locationObj = json.optJSONObject("location")
        val location = locationObj?.let {
            GeoPoint(
                latitude = it.optDouble("latitude", 0.0),
                longitude = it.optDouble("longitude", 0.0),
                accuracyMeters = it.optDouble("accuracy_m", 10.0),
                sharedPrecisely = it.optBoolean("shared_precisely", true),
            )
        }

        val peopleObj = json.optJSONObject("people_affected")
        val peopleVal = peopleObj?.optInt("value", -1)?.takeIf { it >= 0 }
        val peopleRaw = peopleObj?.optString("raw", null)

        val reportedAtIso = json.optString("reported_at", "")
        val reportedAt = try {
            Instant.parse(reportedAtIso)
        } catch (_: Exception) {
            Instant.now()
        }

        val attArr = json.optJSONArray("attachment_ids")
        val attIds = mutableListOf<String>()
        if (attArr != null) {
            for (i in 0 until attArr.length()) {
                val aId = attArr.optString(i)
                if (aId.isNotBlank()) attIds.add(aId)
            }
        }

        return Incident(
            id = id,
            sourceNodeId = json.optString("source_node_id", "gateway"),
            originalText = originalText,
            sourceLanguage = json.optString("source_language", "und"),
            organizationId = json.optString("organization_id", null),
            location = location,
            reportedAt = reportedAt,
            disasterTypes = types,
            severity = json.optInt("severity", 0),
            priorityScore = json.optInt("priority_score", 0),
            priorityClass = priorityClass,
            status = status,
            verificationStatus = VerificationStatus.AI_CLASSIFIED,
            peopleAffected = Quantity(value = peopleVal, raw = peopleRaw),
            attachmentIds = attIds,
        )
    }

    companion object {
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"
        const val DEFAULT_API_KEY = "dev-coordinator-key"
    }
}
