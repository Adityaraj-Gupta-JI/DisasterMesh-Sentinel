package org.disastermesh.sentinel.domain

/**
 * Deterministic priority engine, mirroring `protocol/dms/priority/engine.py`.
 *
 * The AI proposes; this object decides. A rule-triggered life threat sets a floor
 * that low model confidence cannot lower — only a human coordinator can override it,
 * and the override is logged with its reason.
 */
object PriorityEngine {

    const val POLICY_VERSION = "policy-1.0.0"

    private val URGENCY_BASE = mapOf(
        Urgency.CRITICAL to 60, Urgency.HIGH to 40, Urgency.MEDIUM to 20,
        Urgency.LOW to 8, Urgency.UNKNOWN to 15,
    )

    private val LIFE_THREAT = setOf(ConditionType.NOT_BREATHING, ConditionType.UNCONSCIOUS)
    private val ACTIVE_HAZARDS = setOf(
        DisasterType.FIRE, DisasterType.FLOOD, DisasterType.BUILDING_COLLAPSE,
        DisasterType.LANDSLIDE,
    )

    private val TTL_SECONDS = mapOf(
        PriorityClass.P0 to 6 * 3600L, PriorityClass.P1 to 12 * 3600L,
        PriorityClass.P2 to 24 * 3600L, PriorityClass.P3 to 48 * 3600L,
    )

    private val REPLICATION_LIMIT = mapOf(
        PriorityClass.P0 to 8, PriorityClass.P1 to 6, PriorityClass.P2 to 3, PriorityClass.P3 to 2,
    )

    data class Inputs(
        val urgency: Urgency = Urgency.UNKNOWN,
        val severity: Int = 0,
        val disasterTypes: List<DisasterType> = emptyList(),
        val confidence: Double = 0.0,
        val peopleAffected: Quantity = Quantity.unknown(),
        val conditions: List<Condition> = emptyList(),
        val hazards: List<String> = emptyList(),
        val messageAgeSeconds: Double = 0.0,
        val humanVerified: Boolean = false,
        val aiAvailable: Boolean = true,
    )

    data class Decision(
        val score: Int,
        val priorityClass: PriorityClass,
        val ttlSeconds: Long,
        val replicationLimit: Int,
        val allowedRoles: List<Role>,
        val sensitivity: Sensitivity,
        val requiresAck: Boolean,
        val textBeforeMedia: Boolean,
        val explanation: List<String>,
        val escalatedByRule: Boolean,
        val policyVersion: String = POLICY_VERSION,
    )

    fun evaluate(inputs: Inputs): Decision {
        val why = mutableListOf<String>()
        var score = URGENCY_BASE.getValue(inputs.urgency)
        why += "urgency ${inputs.urgency} → base $score"
        if (!inputs.aiAvailable) why += "AI unavailable → rule-only evaluation"

        val severityPoints = Math.round(inputs.severity * 0.20).toInt()
        score += severityPoints
        why += "severity ${inputs.severity} → +$severityPoints"

        val conditionTypes = inputs.conditions.map { it.type }.toSet()
        var floor = 0
        var escalated = false

        if (conditionTypes.any { it in LIFE_THREAT }) {
            floor = maxOf(floor, 85); escalated = true
            why += "RULE: unconscious/not breathing → P0 floor 85"
        }
        val activeHazard = inputs.disasterTypes.any { it in ACTIVE_HAZARDS } || inputs.hazards.isNotEmpty()
        if (ConditionType.TRAPPED in conditionTypes) {
            if (activeHazard) {
                floor = maxOf(floor, 85); escalated = true
                why += "RULE: trapped person with active hazard → P0 floor 85"
            } else {
                floor = maxOf(floor, 60); escalated = true
                why += "RULE: trapped person → P1 floor 60"
            }
        }
        if (DisasterType.FIRE in inputs.disasterTypes &&
            (!inputs.peopleAffected.isUnknown || conditionTypes.isNotEmpty())
        ) {
            floor = maxOf(floor, 60); escalated = true
            why += "RULE: active fire near people → P1 floor 60"
        }

        val people = inputs.peopleAffected
        if (people.isUnknown) {
            why += "people affected unknown → no adjustment (never guessed)"
        } else {
            val points = minOf(12, (people.value ?: 0) * 2)
            score += points
            why += "${people.value} people affected → +$points"
        }

        if (inputs.humanVerified) {
            score += 6; why += "human verified → +6"
        } else if (inputs.confidence < 0.5 && !escalated) {
            score -= 4; why += "low AI confidence, no rule trigger → -4"
        }

        val ageMinutes = inputs.messageAgeSeconds / 60.0
        if (ageMinutes > 60) {
            val decay = minOf(10, ((ageMinutes - 60) / 30).toInt())
            score -= decay
            why += "age ${ageMinutes.toInt()} min → -$decay"
        }

        score = score.coerceIn(0, 100)
        if (floor > 0 && score < floor) {
            why += "rule floor raised score $score → $floor"
            score = floor
        }

        val priority = when {
            score >= 85 -> PriorityClass.P0
            score >= 60 -> PriorityClass.P1
            score >= 30 -> PriorityClass.P2
            else -> PriorityClass.P3
        }

        val medical = DisasterType.MEDICAL in inputs.disasterTypes ||
            conditionTypes.minus(ConditionType.OTHER).isNotEmpty()
        val sensitivity = if (medical) Sensitivity.MEDICAL else Sensitivity.OPERATIONAL
        val allowed = if (medical) {
            why += "medical content → restricted roles; relays carry ciphertext only"
            listOf(
                Role.EVENT_COORDINATOR, Role.MEDICAL_RESPONDER, Role.GOVERNMENT_AUTHORITY,
                Role.VOLUNTEER_RELAY,
            )
        } else emptyList()

        return Decision(
            score = score,
            priorityClass = priority,
            ttlSeconds = TTL_SECONDS.getValue(priority),
            replicationLimit = REPLICATION_LIMIT.getValue(priority),
            allowedRoles = allowed,
            sensitivity = sensitivity,
            requiresAck = priority == PriorityClass.P0 || priority == PriorityClass.P1,
            textBeforeMedia = true,
            explanation = why,
            escalatedByRule = escalated,
        )
    }
}
