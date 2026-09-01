package org.disastermesh.sentinel.domain

import java.time.Instant

/**
 * Canonical domain model, mirroring `protocol/dms/domain/models.py`.
 *
 * Nothing in this file imports Android or transport types: the same rules must hold
 * whether the code runs on a phone, in the simulator, or on the gateway.
 */

const val SCHEMA_VERSION = "1.0.0"

enum class Urgency { CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN }

enum class DisasterType {
    FIRE, FLOOD, EARTHQUAKE, BUILDING_COLLAPSE, MEDICAL, LANDSLIDE, ACCIDENT,
    TRAPPED_PERSON, MISSING_PERSON, LOGISTICS, OTHER
}

enum class PriorityClass(val rank: Int) { P0(0), P1(1), P2(2), P3(3) }

enum class IncidentStatus {
    DRAFT, QUEUED, RELAYED, RECEIVED, ACKNOWLEDGED, DISPATCH_REQUESTED, DISPATCHED,
    EN_ROUTE, ARRIVED, RESOLVED, EXPIRED, CANCELLED
}

enum class VerificationStatus { UNVERIFIED, AI_CLASSIFIED, HUMAN_VERIFIED, DISPUTED }

enum class Sensitivity { PUBLIC, OPERATIONAL, MEDICAL }

enum class PayloadType {
    INCIDENT_TEXT, INCIDENT_UPDATE, ATTACHMENT_MANIFEST, ATTACHMENT_CHUNK,
    ACKNOWLEDGEMENT, DISPATCH_ORDER, EVENT_LOG
}

enum class AttachmentKind { IMAGE, AUDIO, DOCUMENT }

enum class ConditionType {
    TRAPPED, MISSING, DEAD, UNCONSCIOUS, BLEEDING, NOT_BREATHING, INJURY, OTHER
}

enum class Role {
    CITIZEN_REPORTER, VOLUNTEER_RELAY, EVENT_COORDINATOR, MEDICAL_RESPONDER,
    FLOOD_RESPONDER, GOVERNMENT_AUTHORITY, SYSTEM_ADMINISTRATOR
}

enum class Permission {
    CREATE_INCIDENT, FORWARD_BUNDLE, VIEW_INCIDENT, VIEW_MEDICAL_DATA,
    VIEW_PRECISE_LOCATION, PUBLISH_ALERT, ASSIGN_RESOURCE, CLOSE_INCIDENT,
    EXPORT_AUDIT, REVOKE_NODE
}

enum class Provenance { HUMAN_REPORTED, HUMAN_VERIFIED, MACHINE_GENERATED, RULE_ENGINE, IMPORTED }

/**
 * A count that may be unknown or approximate.
 *
 * A vague phrase must never become an exact number: it is stored with a null [value]
 * and the original wording preserved in [raw].
 */
data class Quantity(
    val value: Int? = null,
    val raw: String? = null,
    val approximate: Boolean = false,
    val confidence: Double? = null,
) {
    val isUnknown: Boolean get() = value == null

    companion object {
        fun unknown(raw: String? = null) = Quantity(value = null, raw = raw, approximate = true)
    }
}

/** A location with explicit precision. Precision is recorded, never assumed. */
data class GeoPoint(
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Double? = null,
    val sharedPrecisely: Boolean = true,
) {
    init {
        require(latitude in -90.0..90.0) { "latitude out of range" }
        require(longitude in -180.0..180.0) { "longitude out of range" }
    }

    /** Blur to roughly a kilometre for actors without VIEW_PRECISE_LOCATION. */
    fun coarse(): GeoPoint = copy(
        latitude = Math.round(latitude * 100.0) / 100.0,
        longitude = Math.round(longitude * 100.0) / 100.0,
        accuracyMeters = maxOf(accuracyMeters ?: 0.0, 1000.0),
        sharedPrecisely = false,
    )
}

data class Condition(
    val type: ConditionType,
    val raw: String? = null,
    val confidence: Double? = null,
)

data class AccessPolicy(
    val sensitivity: Sensitivity = Sensitivity.OPERATIONAL,
    val allowedRoles: List<Role> = emptyList(),
    val organizationId: String? = null,
)

/** The central entity. [originalText] is immutable user input and is never rewritten. */
data class Incident(
    val id: String,
    val sourceNodeId: String,
    val originalText: String,
    val sourceLanguage: String = "und",
    val organizationId: String? = null,
    val location: GeoPoint? = null,
    val reportedAt: Instant,
    val expiresAt: Instant? = null,
    val disasterTypes: List<DisasterType> = emptyList(),
    val urgency: Urgency = Urgency.UNKNOWN,
    val severity: Int = 0,
    val classificationConfidence: Double = 0.0,
    val peopleAffected: Quantity = Quantity.unknown(),
    val conditions: List<Condition> = emptyList(),
    val requestedResources: List<String> = emptyList(),
    val priorityScore: Int = 0,
    val priorityClass: PriorityClass = PriorityClass.P3,
    val priorityExplanation: List<String> = emptyList(),
    val policyVersion: String = "policy-1.0.0",
    val status: IncidentStatus = IncidentStatus.DRAFT,
    val verificationStatus: VerificationStatus = VerificationStatus.UNVERIFIED,
    val accessPolicy: AccessPolicy = AccessPolicy(),
    val attachmentIds: List<String> = emptyList(),
    val audioReference: String? = null,
    val provenance: Provenance = Provenance.HUMAN_REPORTED,
    val revision: Int = 1,
    val schemaVersion: String = SCHEMA_VERSION,
    val updatedAt: Instant = reportedAt,
) {
    init {
        require(sourceNodeId.isNotBlank()) { "incident requires a source node id" }
        require(originalText.isNotBlank() || audioReference != null) {
            "incident needs original text or an original audio reference"
        }
        require(severity in 0..100) { "severity must be within 0..100" }
        require(priorityScore in 0..100) { "priority score must be within 0..100" }
    }

    fun isExpired(now: Instant): Boolean = expiresAt?.isBefore(now) == true
}

data class Attachment(
    val id: String,
    val incidentId: String,
    val kind: AttachmentKind,
    val fileName: String,
    val mimeType: String,
    val sizeBytes: Long,
    val sha256: String,
    val localPath: String? = null,
    val committed: Boolean = false,
)

data class Acknowledgement(
    val id: String,
    val incidentId: String,
    val nodeId: String,
    val actorRole: Role,
    val note: String? = null,
    val createdAt: Instant,
) {
    /** Duplicate acknowledgements collapse on this key. */
    val dedupKey: String get() = "$incidentId:$nodeId"
}

val ROLE_PERMISSIONS: Map<Role, Set<Permission>> = mapOf(
    Role.CITIZEN_REPORTER to setOf(Permission.CREATE_INCIDENT, Permission.VIEW_INCIDENT),
    Role.VOLUNTEER_RELAY to setOf(Permission.FORWARD_BUNDLE),
    Role.EVENT_COORDINATOR to setOf(
        Permission.CREATE_INCIDENT, Permission.FORWARD_BUNDLE, Permission.VIEW_INCIDENT,
        Permission.VIEW_MEDICAL_DATA, Permission.VIEW_PRECISE_LOCATION,
        Permission.ASSIGN_RESOURCE, Permission.CLOSE_INCIDENT,
    ),
    Role.MEDICAL_RESPONDER to setOf(
        Permission.VIEW_INCIDENT, Permission.VIEW_MEDICAL_DATA,
        Permission.VIEW_PRECISE_LOCATION, Permission.FORWARD_BUNDLE,
    ),
    Role.FLOOD_RESPONDER to setOf(
        Permission.VIEW_INCIDENT, Permission.VIEW_PRECISE_LOCATION, Permission.FORWARD_BUNDLE,
    ),
    Role.GOVERNMENT_AUTHORITY to setOf(
        Permission.VIEW_INCIDENT, Permission.VIEW_PRECISE_LOCATION, Permission.PUBLISH_ALERT,
        Permission.ASSIGN_RESOURCE, Permission.CLOSE_INCIDENT, Permission.EXPORT_AUDIT,
    ),
    Role.SYSTEM_ADMINISTRATOR to setOf(
        Permission.VIEW_INCIDENT, Permission.EXPORT_AUDIT, Permission.REVOKE_NODE,
        Permission.FORWARD_BUNDLE,
    ),
)

fun Role.can(permission: Permission): Boolean =
    ROLE_PERMISSIONS[this]?.contains(permission) == true

/** Carrying is not reading: a relay never sees plaintext above PUBLIC. */
fun Role.canReadPlaintext(sensitivity: Sensitivity): Boolean = when {
    this == Role.VOLUNTEER_RELAY -> sensitivity == Sensitivity.PUBLIC
    sensitivity == Sensitivity.MEDICAL -> can(Permission.VIEW_MEDICAL_DATA)
    else -> can(Permission.VIEW_INCIDENT) || can(Permission.FORWARD_BUNDLE)
}
