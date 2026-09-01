package org.disastermesh.sentinel.domain

/** Incident lifecycle rules, mirroring `protocol/dms/domain/lifecycle.py`. */
object Lifecycle {

    private val TRANSITIONS: Map<IncidentStatus, Set<IncidentStatus>> = mapOf(
        IncidentStatus.DRAFT to setOf(IncidentStatus.QUEUED, IncidentStatus.CANCELLED),
        IncidentStatus.QUEUED to setOf(
            IncidentStatus.RELAYED, IncidentStatus.RECEIVED, IncidentStatus.EXPIRED,
            IncidentStatus.CANCELLED,
        ),
        IncidentStatus.RELAYED to setOf(
            IncidentStatus.RELAYED, IncidentStatus.RECEIVED, IncidentStatus.EXPIRED,
            IncidentStatus.CANCELLED,
        ),
        IncidentStatus.RECEIVED to setOf(
            IncidentStatus.ACKNOWLEDGED, IncidentStatus.EXPIRED, IncidentStatus.CANCELLED,
        ),
        IncidentStatus.ACKNOWLEDGED to setOf(
            IncidentStatus.DISPATCH_REQUESTED, IncidentStatus.RESOLVED,
            IncidentStatus.EXPIRED, IncidentStatus.CANCELLED,
        ),
        IncidentStatus.DISPATCH_REQUESTED to setOf(
            IncidentStatus.DISPATCHED, IncidentStatus.RESOLVED, IncidentStatus.CANCELLED,
        ),
        IncidentStatus.DISPATCHED to setOf(
            IncidentStatus.EN_ROUTE, IncidentStatus.RESOLVED, IncidentStatus.CANCELLED,
        ),
        IncidentStatus.EN_ROUTE to setOf(
            IncidentStatus.ARRIVED, IncidentStatus.RESOLVED, IncidentStatus.CANCELLED,
        ),
        IncidentStatus.ARRIVED to setOf(IncidentStatus.RESOLVED, IncidentStatus.CANCELLED),
        IncidentStatus.RESOLVED to emptySet(),
        // Expiry hides an incident from routine sync; it never erases it, and a
        // coordinator can still acknowledge or close what expired.
        IncidentStatus.EXPIRED to setOf(IncidentStatus.ACKNOWLEDGED, IncidentStatus.RESOLVED),
        IncidentStatus.CANCELLED to emptySet(),
    )

    private val REQUIRED_PERMISSION: Map<IncidentStatus, Permission> = mapOf(
        IncidentStatus.RESOLVED to Permission.CLOSE_INCIDENT,
        IncidentStatus.DISPATCH_REQUESTED to Permission.ASSIGN_RESOURCE,
        IncidentStatus.DISPATCHED to Permission.ASSIGN_RESOURCE,
    )

    fun canTransition(from: IncidentStatus, to: IncidentStatus): Boolean =
        TRANSITIONS[from]?.contains(to) == true

    fun isAuthorized(to: IncidentStatus, role: Role): Boolean =
        REQUIRED_PERMISSION[to]?.let { role.can(it) } ?: true

    sealed interface Result {
        data class Changed(val incident: Incident) : Result
        /** Duplicate delivery is normal in a mesh: repeating a transition is not an error. */
        data object AlreadyThere : Result
        data class Rejected(val reason: String) : Result
    }

    fun transition(incident: Incident, to: IncidentStatus, role: Role): Result = when {
        incident.status == to -> Result.AlreadyThere
        !canTransition(incident.status, to) ->
            Result.Rejected("illegal transition ${incident.status} -> $to")
        !isAuthorized(to, role) -> Result.Rejected("role $role is not permitted to set $to")
        else -> Result.Changed(incident.copy(status = to, revision = incident.revision + 1))
    }
}
