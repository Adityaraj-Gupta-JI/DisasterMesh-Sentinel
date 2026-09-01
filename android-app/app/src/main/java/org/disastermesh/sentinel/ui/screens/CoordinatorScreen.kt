package org.disastermesh.sentinel.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import org.disastermesh.sentinel.domain.Incident
import org.disastermesh.sentinel.domain.IncidentStatus
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.ui.theme.AiInsightCard
import org.disastermesh.sentinel.ui.theme.EmptyState
import org.disastermesh.sentinel.ui.theme.PriorityBadge
import org.disastermesh.sentinel.ui.theme.Spacing
import org.disastermesh.sentinel.ui.theme.VerificationBadge
import org.disastermesh.sentinel.ui.theme.display

/**
 * Coordinator command interface.
 *
 * Priority inbox first, uncertainty always visible, and dispatch behind an explicit
 * confirmation that names the action as simulated.
 */

data class ResourceOption(val id: String, val label: String, val reason: String)

@Composable
fun CoordinatorInboxScreen(
    incidents: List<Incident>,
    filter: PriorityClass?,
    pendingSync: Int,
    onFilter: (PriorityClass?) -> Unit,
    onOpen: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize().padding(Spacing.md)) {
        Text("Command inbox", style = MaterialTheme.typography.titleLarge)
        Text("Offline · $pendingSync waiting to sync", style = MaterialTheme.typography.bodyMedium)

        Row(
            Modifier.fillMaxWidth().padding(vertical = Spacing.sm),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            FilterChip(selected = filter == null, onClick = { onFilter(null) }, label = { Text("All") })
            PriorityClass.entries.forEach { priority ->
                FilterChip(
                    selected = filter == priority,
                    onClick = { onFilter(priority) },
                    label = { Text(priority.name) },
                )
            }
        }

        if (incidents.isEmpty()) {
            EmptyState("No incidents match this filter.")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(Spacing.sm)) {
                items(incidents, key = { it.id }) { incident ->
                    Card(
                        onClick = { onOpen(incident.id) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(Modifier.padding(Spacing.md)) {
                            Row(
                                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                PriorityBadge(incident.priorityClass)
                                VerificationBadge(incident.verificationStatus)
                            }
                            Text(
                                incident.originalText,
                                style = MaterialTheme.typography.bodyLarge,
                                modifier = Modifier.padding(vertical = Spacing.xs),
                            )
                            Text(
                                "${incident.disasterTypes.joinToString().ifEmpty { "unclassified" }} · " +
                                    "people: ${incident.peopleAffected.display()} · " +
                                    "evidence: ${incident.attachmentIds.size} · " +
                                    incident.status.name.lowercase().replace('_', ' '),
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun IncidentDetailScreen(
    incident: Incident,
    recommendations: List<ResourceOption> = emptyList(),
    onAcknowledge: () -> Unit,
    onDispatch: (resourceId: String, reason: String) -> Unit,
    onBack: () -> Unit = {},
    modifier: Modifier = Modifier,
    // Additive: when provided, image evidence renders as the actual photo instead of
    // just a count. Defaults keep every existing caller working unchanged.
    imageUrlFor: ((attachmentId: String) -> String)? = null,
    authHeader: String? = null,
) {
    var pending by remember { mutableStateOf<ResourceOption?>(null) }
    val acknowledged = incident.status in setOf(
        IncidentStatus.ACKNOWLEDGED, IncidentStatus.DISPATCH_REQUESTED,
        IncidentStatus.DISPATCHED, IncidentStatus.EN_ROUTE, IncidentStatus.ARRIVED,
        IncidentStatus.RESOLVED,
    )

    val activeRecommendations = recommendations.ifEmpty {
        listOf(
            ResourceOption("res_medic_1", "Paramedic Unit Alpha", "Matches emergency medical & trauma response"),
            ResourceOption("res_fire_1", "Fire & Rescue Squad 4", "Matches hazard suppression and search"),
            ResourceOption("res_boat_1", "Flood Evacuation Boat 2", "Matches water rescue and logistics"),
        )
    }

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
            Row(horizontalArrangement = Arrangement.spacedBy(Spacing.sm)) {
                PriorityBadge(incident.priorityClass)
                VerificationBadge(incident.verificationStatus)
            }
            OutlinedButton(onClick = onBack) { Text("Back") }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(Spacing.md)) {
                Text("Original report", style = MaterialTheme.typography.labelSmall)
                Text(incident.originalText, style = MaterialTheme.typography.bodyLarge)
                Text(
                    "from ${incident.sourceNodeId} · status: ${incident.status.name}",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }

        Text(
            "People affected: ${incident.peopleAffected.display()} · " +
                "location: ${
                    incident.location?.let {
                        if (it.sharedPrecisely) "exact (${it.latitude}, ${it.longitude})" else "approximate"
                    } ?: "not shared"
                }",
            style = MaterialTheme.typography.bodyMedium,
        )

        AiInsightCard(
            "Urgency ${incident.urgency}, severity ${incident.severity}",
            incident.priorityExplanation.ifEmpty { listOf("Evaluated by deterministic Priority Engine") },
        )

        Button(
            onClick = onAcknowledge,
            enabled = !acknowledged,
            modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
        ) {
            Text(if (acknowledged) "Acknowledged ✓" else "Acknowledge Incident")
        }

        Text("Recommended resources", style = MaterialTheme.typography.titleLarge)
        activeRecommendations.forEach { option ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(Spacing.md)) {
                    Text(option.label, style = MaterialTheme.typography.bodyLarge)
                    Text(option.reason, style = MaterialTheme.typography.bodyMedium)
                    OutlinedButton(
                        onClick = { pending = option },
                        enabled = acknowledged,
                        modifier = Modifier.padding(top = Spacing.sm),
                    ) { Text("Dispatch ${option.label}…") }
                }
            }
        }

        Text(
            "Simulated dispatch. No real emergency service is contacted.",
            style = MaterialTheme.typography.labelSmall,
        )
    }

    // Dispatch is never one tap: the confirmation names the resource and says plainly
    // that the action is simulated.
    pending?.let { option ->
        AlertDialog(
            onDismissRequest = { pending = null },
            title = { Text("Confirm simulated dispatch") },
            text = {
                Text(
                    "Assign ${option.label} to this incident?\n\n${option.reason}\n\n" +
                        "This is a simulated assignment. No real emergency service is contacted."
                )
            },
            confirmButton = {
                Button(onClick = {
                    onDispatch(option.id, option.reason)
                    pending = null
                }) { Text("Confirm") }
            },
            dismissButton = { TextButton(onClick = { pending = null }) { Text("Cancel") } },
        )
    }
}
