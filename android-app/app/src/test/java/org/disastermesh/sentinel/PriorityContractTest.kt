package org.disastermesh.sentinel

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.disastermesh.sentinel.domain.Condition
import org.disastermesh.sentinel.domain.ConditionType
import org.disastermesh.sentinel.domain.DisasterType
import org.disastermesh.sentinel.domain.PriorityEngine
import org.disastermesh.sentinel.domain.Quantity
import org.disastermesh.sentinel.domain.Urgency
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Conformance against the frozen cross-language priority contract.
 *
 * This engine exists twice — here and in Python. Mirrored unit tests do not stop the
 * two drifting apart, because both suites can be edited together. A single frozen file
 * of inputs and expected outputs can not: whichever side changes, its test fails.
 *
 * The contract is generated from the Python reference with
 * `python3 scripts/make_priority_contract.py`. Regenerating is deliberate; the diff is
 * the review.
 *
 * NOT YET EXECUTED — there is no Android SDK on the development machine. Until this
 * runs, `protocol/tests/test_engine_parity.py` compares the two sources structurally
 * as a stand-in.
 */
class PriorityContractTest {

    private val json = Json { ignoreUnknownKeys = true }

    /** Walk up from the working directory: Gradle's test CWD is the module, not the repo. */
    private fun contractFile(): File {
        var directory: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (directory != null) {
            val candidate = File(directory, "test-fixtures/priority-engine-contract.json")
            if (candidate.exists()) return candidate
            directory = directory.parentFile
        }
        throw AssertionError(
            "priority-engine-contract.json not found; run scripts/make_priority_contract.py"
        )
    }

    private fun cases(): List<JsonObject> =
        json.parseToJsonElement(contractFile().readText())
            .jsonObject["cases"]!!.jsonArray.map { it.jsonObject }

    private fun inputsOf(spec: JsonObject): PriorityEngine.Inputs {
        val peopleElement = spec["people"]
        val people = if (peopleElement is JsonObject) peopleElement else null
        val quantity = if (people == null || people["value"]?.jsonPrimitive?.contentOrNull == null) {
            Quantity.unknown(people?.get("raw")?.jsonPrimitive?.contentOrNull)
        } else {
            Quantity(
                value = people["value"]!!.jsonPrimitive.int,
                raw = people["raw"]?.jsonPrimitive?.contentOrNull,
            )
        }
        return PriorityEngine.Inputs(
            urgency = Urgency.valueOf(spec["urgency"]!!.jsonPrimitive.content),
            severity = spec["severity"]!!.jsonPrimitive.int,
            disasterTypes = spec["disaster_types"]!!.jsonArray.map {
                DisasterType.valueOf(it.jsonPrimitive.content)
            },
            confidence = spec["confidence"]!!.jsonPrimitive.content.toDouble(),
            peopleAffected = quantity,
            conditions = spec["conditions"]!!.jsonArray.map {
                Condition(ConditionType.valueOf(it.jsonPrimitive.content))
            },
            hazards = spec["hazards"]!!.jsonArray.map { it.jsonPrimitive.content },
            messageAgeSeconds = spec["age_seconds"]!!.jsonPrimitive.content.toDouble(),
            humanVerified = spec["human_verified"]!!.jsonPrimitive.boolean,
            aiAvailable = spec["ai_available"]!!.jsonPrimitive.boolean,
        )
    }

    @Test
    fun `kotlin engine matches every contract case`() {
        val failures = mutableListOf<String>()

        for (case in cases()) {
            val name = case["name"]!!.jsonPrimitive.content
            val expected = case["expected"]!!.jsonObject
            val decision = PriorityEngine.evaluate(inputsOf(case["inputs"]!!.jsonObject))

            val mismatches = buildList {
                fun check(field: String, actual: Any, want: Any) {
                    if (actual != want) add("$field: expected $want, got $actual")
                }
                check("score", decision.score, expected["score"]!!.jsonPrimitive.int)
                check(
                    "priority_class", decision.priorityClass.name,
                    expected["priority_class"]!!.jsonPrimitive.content,
                )
                check(
                    "ttl_seconds", decision.ttlSeconds,
                    expected["ttl_seconds"]!!.jsonPrimitive.content.toLong(),
                )
                check(
                    "replication_limit", decision.replicationLimit,
                    expected["replication_limit"]!!.jsonPrimitive.int,
                )
                check(
                    "sensitivity", decision.sensitivity.name,
                    expected["sensitivity"]!!.jsonPrimitive.content,
                )
                check(
                    "requires_ack", decision.requiresAck,
                    expected["requires_ack"]!!.jsonPrimitive.boolean,
                )
                check(
                    "escalated_by_rule", decision.escalatedByRule,
                    expected["escalated_by_rule"]!!.jsonPrimitive.boolean,
                )
            }
            if (mismatches.isNotEmpty()) {
                val note = case["note"]?.jsonPrimitive?.contentOrNull ?: "—"
                failures += "case '$name' (note: $note): ${mismatches.joinToString("; ")}"
            }
        }

        assertTrue(
            "the Kotlin engine drifted from the shared contract:\n" +
                failures.joinToString("\n") { "  $it" } +
                "\nIf a change is intended, regenerate the contract and justify the diff.",
            failures.isEmpty(),
        )
    }

    @Test
    fun `contract covers the decision surface`() {
        val all = cases()
        assertTrue("the contract must cover the decision surface", all.size >= 30)
        val classes = all.map { it["expected"]!!.jsonObject["priority_class"]!!.jsonPrimitive.content }
        assertEquals(
            "every priority class must appear in the contract",
            setOf("P0", "P1", "P2", "P3"), classes.toSet(),
        )
    }

    @Test
    fun `life threat cases are pinned to P0`() {
        val lifeThreat = cases().filter { case ->
            case["inputs"]!!.jsonObject["conditions"]!!.jsonArray
                .map { it.jsonPrimitive.content }
                .any { it == "NOT_BREATHING" || it == "UNCONSCIOUS" }
        }
        assertTrue("the contract must pin the life-threat floor", lifeThreat.size >= 3)
        lifeThreat.forEach { case ->
            val expected = case["expected"]!!.jsonObject
            assertEquals("P0", expected["priority_class"]!!.jsonPrimitive.content)
            assertTrue(expected["escalated_by_rule"]!!.jsonPrimitive.boolean)
        }
    }
}
