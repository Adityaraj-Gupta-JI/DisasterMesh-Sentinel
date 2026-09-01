package org.disastermesh.sentinel

import org.disastermesh.sentinel.domain.Condition
import org.disastermesh.sentinel.domain.ConditionType
import org.disastermesh.sentinel.domain.DisasterType
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.domain.PriorityEngine
import org.disastermesh.sentinel.domain.Quantity
import org.disastermesh.sentinel.domain.Sensitivity
import org.disastermesh.sentinel.domain.Urgency
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * These mirror `protocol/tests/test_priority.py` one for one. If the Kotlin engine and
 * the Python engine ever disagree, a phone and the gateway would prioritise the same
 * incident differently — so the expectations are duplicated deliberately.
 *
 * NOT YET EXECUTED: no Gradle/Android SDK on the development machine.
 */
class PriorityEngineTest {

    @Test
    fun `collapse with trapped people is P0`() {
        val decision = PriorityEngine.evaluate(
            PriorityEngine.Inputs(
                urgency = Urgency.CRITICAL,
                severity = 85,
                confidence = 0.9,
                disasterTypes = listOf(DisasterType.BUILDING_COLLAPSE, DisasterType.TRAPPED_PERSON),
                conditions = listOf(Condition(ConditionType.TRAPPED)),
                peopleAffected = Quantity(value = 3, raw = "Three people"),
            )
        )
        assertEquals(PriorityClass.P0, decision.priorityClass)
        assertEquals(85, decision.score)
        assertTrue(decision.requiresAck)
    }

    @Test
    fun `ai uncertainty cannot downgrade a rule-triggered life threat`() {
        val decision = PriorityEngine.evaluate(
            PriorityEngine.Inputs(
                urgency = Urgency.LOW,
                severity = 5,
                confidence = 0.02,
                conditions = listOf(Condition(ConditionType.NOT_BREATHING)),
            )
        )
        assertEquals(PriorityClass.P0, decision.priorityClass)
        assertTrue(decision.escalatedByRule)
        assertTrue(decision.explanation.any { it.startsWith("RULE") })
    }

    @Test
    fun `routine logistics is P3`() {
        val decision = PriorityEngine.evaluate(
            PriorityEngine.Inputs(
                urgency = Urgency.LOW, severity = 12, confidence = 0.8,
                disasterTypes = listOf(DisasterType.LOGISTICS),
            )
        )
        assertEquals(PriorityClass.P3, decision.priorityClass)
    }

    @Test
    fun `unknown people count never adds points`() {
        val unknown = PriorityEngine.evaluate(
            PriorityEngine.Inputs(urgency = Urgency.HIGH, severity = 50)
        )
        val known = PriorityEngine.evaluate(
            PriorityEngine.Inputs(
                urgency = Urgency.HIGH, severity = 50,
                peopleAffected = Quantity(value = 4, raw = "four"),
            )
        )
        assertTrue(known.score > unknown.score)
        assertTrue(unknown.explanation.any { it.contains("unknown") })
    }

    @Test
    fun `medical content restricts roles`() {
        val decision = PriorityEngine.evaluate(
            PriorityEngine.Inputs(
                urgency = Urgency.CRITICAL, severity = 90,
                conditions = listOf(Condition(ConditionType.BLEEDING)),
            )
        )
        assertEquals(Sensitivity.MEDICAL, decision.sensitivity)
        assertTrue(decision.allowedRoles.isNotEmpty())
    }

    @Test
    fun `evaluation is deterministic`() {
        val inputs = PriorityEngine.Inputs(
            urgency = Urgency.HIGH, severity = 64, confidence = 0.71,
            disasterTypes = listOf(DisasterType.FLOOD), peopleAffected = Quantity(value = 2),
        )
        assertEquals(PriorityEngine.evaluate(inputs).score, PriorityEngine.evaluate(inputs).score)
    }
}
