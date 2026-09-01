package org.disastermesh.sentinel.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.disastermesh.sentinel.domain.Incident
import org.disastermesh.sentinel.domain.IncidentStatus
import org.disastermesh.sentinel.ui.theme.AiInsightCard
import org.disastermesh.sentinel.ui.theme.EmptyState
import org.disastermesh.sentinel.ui.theme.NetworkStatusChip
import org.disastermesh.sentinel.ui.theme.PriorityBadge
import org.disastermesh.sentinel.ui.theme.Spacing
import org.disastermesh.sentinel.ui.theme.label

/**
 * Reporter experience.
 *
 * One decision per screen and a single dominant action. Submission never waits for
 * AI, never waits for a network, and always shows the person what happened to their
 * report in plain language.
 */

data class ReporterState(
    val online: Boolean = false,
    val nearbyPeers: Int = 0,
    val queued: Int = 0,
    val acknowledged: Int = 0,
    val myReports: List<Incident> = emptyList(),
    val aiAvailable: Boolean = true,
)

@Composable
fun ReporterHomeScreen(
    state: ReporterState,
    onStartReport: () -> Unit,
    onStartVoiceReport: () -> Unit,
    onOpenReport: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(Spacing.md),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("DisasterMesh Sentinel", style = MaterialTheme.typography.titleLarge)
            NetworkStatusChip(state.online, state.nearbyPeers)
        }

        // The emergency action is the largest thing on the screen and reachable
        // with one thumb.
        Button(
            onClick = onStartReport,
            modifier = Modifier.fillMaxWidth().height(Spacing.emergencyButton),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.error,
            ),
        ) {
            Text("SEND SOS", style = MaterialTheme.typography.displaySmall)
        }

        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.sm)) {
            OutlinedButton(onClick = onStartReport, modifier = Modifier.weight(1f)) {
                Text("Report incident")
            }
            OutlinedButton(onClick = onStartVoiceReport, modifier = Modifier.weight(1f)) {
                Text("Voice")
            }
        }

        Text("My reports", style = MaterialTheme.typography.titleLarge)
        Text(
            "${state.queued} waiting to send · ${state.acknowledged} seen by a coordinator",
            style = MaterialTheme.typography.bodyMedium,
        )

        if (state.myReports.isEmpty()) {
            EmptyState("You have not sent any reports yet.")
        } else {
            state.myReports.forEach { incident ->
                Card(
                    onClick = { onOpenReport(incident.id) },
                    modifier = Modifier.fillMaxWidth().padding(vertical = Spacing.xs),
                ) {
                    Column(Modifier.padding(Spacing.md)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            PriorityBadge(incident.priorityClass)
                        }
                        Text(
                            incident.originalText,
                            style = MaterialTheme.typography.bodyLarge,
                            modifier = Modifier.padding(top = Spacing.sm),
                        )
                        Text(
                            statusMessage(incident.status),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
    }
}

/** Plain language, no jargon: the person needs to know if help knows. */
fun statusMessage(status: IncidentStatus): String = when (status) {
    IncidentStatus.DRAFT -> "Not sent yet."
    IncidentStatus.QUEUED -> "Saved on this phone. It will send when a device is near."
    IncidentStatus.RELAYED -> "Passed to a nearby device."
    IncidentStatus.RECEIVED -> "Delivered to a coordinator."
    IncidentStatus.ACKNOWLEDGED -> "A coordinator has seen your report."
    IncidentStatus.DISPATCH_REQUESTED, IncidentStatus.DISPATCHED -> "Help has been assigned."
    IncidentStatus.EN_ROUTE -> "Help is on the way."
    IncidentStatus.ARRIVED -> "Help has arrived."
    IncidentStatus.RESOLVED -> "This report is closed."
    IncidentStatus.EXPIRED -> "This report is old, but it is still saved."
    IncidentStatus.CANCELLED -> "You cancelled this report."
}

@Composable
fun NewIncidentScreen(
    aiAvailable: Boolean,
    suggestion: Pair<String, List<String>>?,
    submitting: Boolean,
    onSubmit: (
        text: String,
        disasterTypes: List<org.disastermesh.sentinel.domain.DisasterType>,
        urgency: org.disastermesh.sentinel.domain.Urgency,
        peopleCount: Int?,
        shareLocation: Boolean,
    ) -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var text by remember { mutableStateOf("") }
    var shareLocation by remember { mutableStateOf(true) }
    var selectedType by remember { mutableStateOf(org.disastermesh.sentinel.domain.DisasterType.OTHER) }
    var selectedUrgency by remember { mutableStateOf(org.disastermesh.sentinel.domain.Urgency.HIGH) }
    var peopleText by remember { mutableStateOf("") }

    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(Spacing.md),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Report Emergency", style = MaterialTheme.typography.titleLarge)
            OutlinedButton(onClick = onCancel) { Text("Cancel") }
        }

        Text("What is happening?", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = text,
            onValueChange = { text = it },
            modifier = Modifier.fillMaxWidth().height(120.dp),
            placeholder = { Text("Describe the situation, dangers, and immediate needs...") },
        )

        Text("Disaster Type", style = MaterialTheme.typography.titleSmall)
        Row(
            Modifier
                .fillMaxWidth()
                .padding(vertical = Spacing.xs),
            horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
        ) {
            listOf(
                org.disastermesh.sentinel.domain.DisasterType.MEDICAL,
                org.disastermesh.sentinel.domain.DisasterType.FLOOD,
                org.disastermesh.sentinel.domain.DisasterType.FIRE,
                org.disastermesh.sentinel.domain.DisasterType.TRAPPED_PERSON,
            ).forEach { type ->
                androidx.compose.material3.FilterChip(
                    selected = selectedType == type,
                    onClick = { selectedType = type },
                    label = { Text(type.name.replace('_', ' ')) },
                )
            }
        }

        Text("Urgency Level", style = MaterialTheme.typography.titleSmall)
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
        ) {
            listOf(
                org.disastermesh.sentinel.domain.Urgency.CRITICAL,
                org.disastermesh.sentinel.domain.Urgency.HIGH,
                org.disastermesh.sentinel.domain.Urgency.MEDIUM,
            ).forEach { urgency ->
                androidx.compose.material3.FilterChip(
                    selected = selectedUrgency == urgency,
                    onClick = { selectedUrgency = urgency },
                    label = { Text(urgency.name) },
                )
            }
        }

        OutlinedTextField(
            value = peopleText,
            onValueChange = { if (it.all { char -> char.isDigit() }) peopleText = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Number of people affected (optional)") },
            placeholder = { Text("e.g. 2") },
        )

        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = shareLocation, onCheckedChange = { shareLocation = it })
            Text("Share my exact GPS location", style = MaterialTheme.typography.bodyMedium)
        }
        Text(
            if (shareLocation) "Responders will see where you are."
            else "Only an approximate area will be shared.",
            style = MaterialTheme.typography.bodySmall,
        )

        when {
            !aiAvailable -> Text(
                "Automatic analysis is offline. Report will queue locally and relay.",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Medium,
            )
            suggestion != null -> AiInsightCard(suggestion.first, suggestion.second)
        }

        Button(
            onClick = {
                val pCount = peopleText.toIntOrNull()
                onSubmit(text, listOf(selectedType), selectedUrgency, pCount, shareLocation)
            },
            enabled = text.isNotBlank() && !submitting,
            modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
        ) {
            Text(if (submitting) "Submitting Report…" else "Send Emergency Report")
        }
    }
}


@Composable
fun SubmissionConfirmationScreen(
    incident: Incident,
    onAddPhoto: () -> Unit,
    onDone: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier.fillMaxSize().padding(Spacing.md),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        Text("Report sent", style = MaterialTheme.typography.displaySmall)
        PriorityBadge(incident.priorityClass)
        Text(statusMessage(incident.status), style = MaterialTheme.typography.bodyLarge)

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(Spacing.md)) {
                Text("Your words", style = MaterialTheme.typography.labelSmall)
                // The original message is always shown back, never a rewritten version.
                Text(incident.originalText, style = MaterialTheme.typography.bodyLarge)
            }
        }

        Text(
            "Marked ${incident.priorityClass.label()}. A photo can follow — your message " +
                "goes first so it is never held up.",
            style = MaterialTheme.typography.bodyMedium,
        )

        OutlinedButton(
            onClick = onAddPhoto,
            modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
        ) { Text("Add a photo") }
        Button(
            onClick = onDone,
            modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
        ) { Text("Done") }
    }
}
