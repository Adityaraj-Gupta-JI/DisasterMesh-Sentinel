package org.disastermesh.sentinel

import java.time.Instant
import org.disastermesh.sentinel.domain.Incident
import org.disastermesh.sentinel.domain.IncidentStatus
import org.disastermesh.sentinel.domain.Lifecycle
import org.disastermesh.sentinel.domain.Role
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Mirrors `protocol/tests/test_domain.py`. NOT YET EXECUTED — no Android SDK here. */
class LifecycleTest {

    private fun incident(status: IncidentStatus) = Incident(
        id = "inc_1",
        sourceNodeId = "A",
        originalText = "Three people trapped",
        reportedAt = Instant.parse("2026-01-01T00:00:00Z"),
        status = status,
    )

    @Test
    fun `legal transitions are accepted`() {
        val result = Lifecycle.transition(
            incident(IncidentStatus.RECEIVED), IncidentStatus.ACKNOWLEDGED, Role.EVENT_COORDINATOR,
        )
        assertTrue(result is Lifecycle.Result.Changed)
    }

    @Test
    fun `illegal transitions are rejected`() {
        val result = Lifecycle.transition(
            incident(IncidentStatus.DRAFT), IncidentStatus.DISPATCHED, Role.EVENT_COORDINATOR,
        )
        assertTrue(result is Lifecycle.Result.Rejected)
    }

    @Test
    fun `duplicate transition is idempotent, not an error`() {
        val result = Lifecycle.transition(
            incident(IncidentStatus.ACKNOWLEDGED), IncidentStatus.ACKNOWLEDGED,
            Role.EVENT_COORDINATOR,
        )
        assertTrue(result is Lifecycle.Result.AlreadyThere)
    }

    @Test
    fun `closing an incident requires authorization`() {
        assertFalse(Lifecycle.isAuthorized(IncidentStatus.RESOLVED, Role.CITIZEN_REPORTER))
        assertTrue(Lifecycle.isAuthorized(IncidentStatus.RESOLVED, Role.EVENT_COORDINATOR))
    }

    @Test
    fun `an expired incident can still be acknowledged`() {
        assertTrue(Lifecycle.canTransition(IncidentStatus.EXPIRED, IncidentStatus.ACKNOWLEDGED))
    }
}
