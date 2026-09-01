package org.disastermesh.sentinel.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import org.disastermesh.sentinel.R
import org.disastermesh.sentinel.domain.Incident
import org.disastermesh.sentinel.domain.IncidentStatus
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.ui.NoteDraft
import org.disastermesh.sentinel.ui.NoteUi
import org.disastermesh.sentinel.ui.theme.AiInsightCard
import org.disastermesh.sentinel.ui.theme.EmptyState
import org.disastermesh.sentinel.ui.theme.OperationalBlue
import org.disastermesh.sentinel.ui.theme.PriorityBadge
import org.disastermesh.sentinel.ui.theme.RoutineGrey
import org.disastermesh.sentinel.ui.theme.Spacing
import org.disastermesh.sentinel.ui.theme.TextDim
import org.disastermesh.sentinel.ui.theme.TextMicro
import org.disastermesh.sentinel.ui.theme.UrgentOrange
import org.disastermesh.sentinel.ui.theme.VerificationBadge
import org.disastermesh.sentinel.ui.theme.VerifiedGreen
import org.disastermesh.sentinel.ui.theme.display
import org.disastermesh.sentinel.ui.theme.label

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
    imageUrlFor: ((incidentId: String, attachmentId: String) -> String)? = null,
    authHeader: String? = null,
) {
    Column(modifier.fillMaxSize().padding(Spacing.md)) {
        // ── Header ────────────────────────────────────────────────────────────
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
            ) {
                Image(
                    painter = painterResource(id = R.drawable.app_logo),
                    contentDescription = "DisasterMesh Logo",
                    modifier = Modifier
                        .size(36.dp)
                        .clip(RoundedCornerShape(8.dp)),
                )
                Column {
                    Text(
                        "COMMAND INBOX",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "${incidents.size} ACTIVE · $pendingSync PENDING SYNC",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMicro,
                    )
                }
            }
        }

        Spacer(Modifier.height(Spacing.sm))

        // ── Priority filter bar — compact pill strip ──────────────────────────
        LazyRow(
            Modifier.fillMaxWidth().padding(vertical = Spacing.xs),
            horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
        ) {
            item {
                FilterChip(
                    selected = filter == null,
                    onClick = { onFilter(null) },
                    label = { Text("ALL", style = MaterialTheme.typography.labelSmall) },
                )
            }
            items(PriorityClass.entries) { priority ->
                FilterChip(
                    selected = filter == priority,
                    onClick = { onFilter(priority) },
                    label = { Text(priority.name, style = MaterialTheme.typography.labelSmall) },
                )
            }
        }

        Spacer(Modifier.height(Spacing.xs))

        // ── Incident list — dense rows ────────────────────────────────────────
        if (incidents.isEmpty()) {
            EmptyState("No incidents match this filter.")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(0.dp)) {
                items(incidents, key = { it.id }) { incident ->
                    CoordinatorIncidentRow(
                        incident = incident,
                        onClick = { onOpen(incident.id) },
                        imageUrlFor = imageUrlFor,
                        authHeader = authHeader,
                    )
                }
            }
        }
    }
}

/** Dense coordinator inbox row — priority edge + badges + title + metadata + photos. */
@Composable
private fun CoordinatorIncidentRow(
    incident: Incident,
    onClick: () -> Unit,
    imageUrlFor: ((incidentId: String, attachmentId: String) -> String)? = null,
    authHeader: String? = null,
) {
    val priorityColor = when (incident.priorityClass) {
        PriorityClass.P0 -> org.disastermesh.sentinel.ui.theme.CriticalRed
        PriorityClass.P1 -> UrgentOrange
        PriorityClass.P2 -> OperationalBlue
        PriorityClass.P3 -> RoutineGrey
    }
    val isAcknowledged = incident.status in setOf(
        IncidentStatus.ACKNOWLEDGED, IncidentStatus.DISPATCH_REQUESTED,
        IncidentStatus.DISPATCHED, IncidentStatus.EN_ROUTE, IncidentStatus.ARRIVED,
        IncidentStatus.RESOLVED,
    )

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = Spacing.sm),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
    ) {
        // Priority edge accent
        Box(
            Modifier
                .width(3.dp)
                .height(60.dp)
                .background(priorityColor, RoundedCornerShape(2.dp)),
        )

        Column(Modifier.weight(1f)) {
            // Badge row
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                PriorityBadge(incident.priorityClass)
                VerificationBadge(incident.verificationStatus)
                if (isAcknowledged) {
                    org.disastermesh.sentinel.ui.theme.Badge(
                        text = "ACK'D",
                        color = VerifiedGreen,
                        filled = false,
                    )
                }
            }

            // Incident text — dominant
            Text(
                incident.originalText,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                modifier = Modifier.padding(top = 3.dp),
            )

            // Metadata
            Text(
                "${incident.disasterTypes.joinToString().ifEmpty { "unclassified" }} · " +
                    "people: ${incident.peopleAffected.display()} · " +
                    "${incident.attachmentIds.size} evidence · " +
                    incident.status.name.lowercase().replace('_', ' '),
                style = MaterialTheme.typography.labelSmall,
                color = TextDim,
                modifier = Modifier.padding(top = 2.dp),
                maxLines = 1,
            )

            // Render photo thumbnails if present
            if (imageUrlFor != null && incident.attachmentIds.isNotEmpty()) {
                incident.attachmentIds.forEach { attId ->
                    AsyncImage(
                        model = ImageRequest.Builder(LocalContext.current)
                            .data(imageUrlFor(incident.id, attId))
                            .apply {
                                if (authHeader != null) {
                                    addHeader("Authorization", authHeader)
                                }
                            }
                            .crossfade(true)
                            .build(),
                        contentDescription = "Photo evidence",
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 200.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .padding(top = Spacing.xs),
                    )
                }
            }
        }
    }

    // Row separator
    Box(
        Modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(RoutineGrey.copy(alpha = 0.10f)),
    )
}

@Composable
fun IncidentDetailScreen(
    incident: Incident,
    recommendations: List<ResourceOption> = emptyList(),
    onAcknowledge: () -> Unit,
    onDispatch: (resourceId: String, reason: String) -> Unit,
    onBack: () -> Unit = {},
    modifier: Modifier = Modifier,
    imageUrlFor: ((attachmentId: String) -> String)? = null,
    authHeader: String? = null,
    notes: List<NoteUi> = emptyList(),
    noteDraft: NoteDraft? = null,
    isRecordingNote: Boolean = false,
    onStartVoiceNote: () -> Unit = {},
    onStopVoiceNote: () -> Unit = {},
    onStartTextNote: () -> Unit = {},
    onNoteDraftTextChange: (String) -> Unit = {},
    onSaveNoteDraft: () -> Unit = {},
    onCancelNoteDraft: () -> Unit = {},
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
        // ── Header ────────────────────────────────────────────────────────────
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(Spacing.xs)) {
                PriorityBadge(incident.priorityClass)
                VerificationBadge(incident.verificationStatus)
            }
            OutlinedButton(
                onClick = onBack,
                shape = RoundedCornerShape(4.dp),
            ) {
                Text("Back", style = MaterialTheme.typography.labelLarge)
            }
        }

        // ── Hero text ────────────────────────────────────────────────────────
        Column(
            Modifier
                .fillMaxWidth()
                .background(
                    MaterialTheme.colorScheme.surfaceVariant,
                    RoundedCornerShape(4.dp),
                )
                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp))
                .padding(Spacing.md),
        ) {
            Text(
                "ORIGINAL REPORT",
                style = MaterialTheme.typography.labelSmall,
                color = TextMicro,
            )
            Spacer(Modifier.height(Spacing.xs))
            Text(
                incident.originalText,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(Spacing.xs))
            Text(
                "from ${incident.sourceNodeId} · ${incident.status.name.lowercase().replace('_', ' ')}",
                style = MaterialTheme.typography.labelSmall,
                color = TextMicro,
            )
        }

        // ── Metadata strip ────────────────────────────────────────────────────
        Text(
            "people: ${incident.peopleAffected.display()} · " +
                "location: ${
                    incident.location?.let {
                        if (it.sharedPrecisely) "exact (${it.latitude}, ${it.longitude})"
                        else "approximate"
                    } ?: "not shared"
                } · evidence: ${incident.attachmentIds.size}",
            style = MaterialTheme.typography.bodySmall,
            color = TextDim,
        )

        // ── Attached Evidence Photos ──────────────────────────────────────────
        if (imageUrlFor != null && incident.attachmentIds.isNotEmpty()) {
            Text(
                "PHOTO EVIDENCE (${incident.attachmentIds.size})",
                style = MaterialTheme.typography.titleMedium,
                color = TextMicro,
            )
            incident.attachmentIds.forEach { attId ->
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current)
                        .data(imageUrlFor(attId))
                        .apply {
                            if (authHeader != null) {
                                addHeader("Authorization", authHeader)
                            }
                        }
                        .crossfade(true)
                        .build(),
                    contentDescription = "Photo evidence",
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 280.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp)),
                )
            }
        }

        // ── AI intelligence ────────────────────────────────────────────────────
        AiInsightCard(
            "Urgency ${incident.urgency}, severity ${incident.severity}",
            incident.priorityExplanation.ifEmpty { listOf("Evaluated by deterministic Priority Engine") },
        )

        // ── Acknowledge ────────────────────────────────────────────────────────
        Button(
            onClick = onAcknowledge,
            enabled = !acknowledged,
            modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
            shape = RoundedCornerShape(4.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (acknowledged) VerifiedGreen.copy(alpha = 0.30f)
                else VerifiedGreen,
            ),
        ) {
            Text(
                if (acknowledged) "ACKNOWLEDGED ✓" else "ACKNOWLEDGE INCIDENT",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
            )
        }

        // ── Coordinator notes ──────────────────────────────────────────────────
        Text(
            "COORDINATOR NOTES",
            style = MaterialTheme.typography.titleMedium,
            color = TextMicro,
        )
        if (notes.isEmpty() && noteDraft == null) {
            EmptyState("No follow-up notes yet.")
        }
        notes.forEach { note ->
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(4.dp))
                    .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp))
                    .padding(Spacing.md),
            ) {
                Text(note.text, style = MaterialTheme.typography.bodyMedium)
                Text(
                    if (note.source == "voice") "🎤 voice note" else "typed note",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMicro,
                )
            }
        }
        if (noteDraft == null) {
            Row(horizontalArrangement = Arrangement.spacedBy(Spacing.sm)) {
                if (!isRecordingNote) {
                    OutlinedButton(
                        onClick = onStartVoiceNote,
                        shape = RoundedCornerShape(4.dp),
                    ) { Text("🎤 Record note", style = MaterialTheme.typography.labelLarge) }
                } else {
                    OutlinedButton(
                        onClick = onStopVoiceNote,
                        shape = RoundedCornerShape(4.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = org.disastermesh.sentinel.ui.theme.CriticalRed),
                    ) { Text("■ STOP", style = MaterialTheme.typography.labelLarge) }
                }
                OutlinedButton(
                    onClick = onStartTextNote,
                    shape = RoundedCornerShape(4.dp),
                ) { Text("+ Type a note", style = MaterialTheme.typography.labelLarge) }
            }
        } else {
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(4.dp))
                    .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp))
                    .padding(Spacing.md),
            ) {
                OutlinedTextField(
                    value = noteDraft.text,
                    onValueChange = onNoteDraftTextChange,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !noteDraft.busy,
                    placeholder = { Text(if (noteDraft.busy) "Transcribing…" else "Note text…") },
                    shape = RoundedCornerShape(4.dp),
                )
                Row(
                    Modifier.padding(top = Spacing.sm),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                ) {
                    Button(
                        onClick = onSaveNoteDraft,
                        enabled = !noteDraft.busy && noteDraft.text.isNotBlank(),
                        shape = RoundedCornerShape(4.dp),
                    ) {
                        Text(
                            if (noteDraft.busy) "SAVING…" else "SAVE NOTE",
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                    OutlinedButton(
                        onClick = onCancelNoteDraft,
                        enabled = !noteDraft.busy,
                        shape = RoundedCornerShape(4.dp),
                    ) {
                        Text("Cancel", style = MaterialTheme.typography.labelLarge)
                    }
                }
            }
        }

        // ── Recommended resources — compact rows ──────────────────────────────
        Text(
            "RECOMMENDED RESOURCES",
            style = MaterialTheme.typography.titleMedium,
            color = TextMicro,
        )
        Column(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(4.dp))
                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp))
                .padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(0.dp),
        ) {
            activeRecommendations.forEachIndexed { idx, option ->
                Column(Modifier.fillMaxWidth().padding(vertical = Spacing.sm)) {
                    Text(
                        option.label,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        option.reason,
                        style = MaterialTheme.typography.bodySmall,
                        color = TextDim,
                    )
                    OutlinedButton(
                        onClick = { pending = option },
                        enabled = acknowledged,
                        modifier = Modifier.padding(top = Spacing.xs),
                        shape = RoundedCornerShape(4.dp),
                    ) {
                        Text(
                            "Dispatch ${option.label}…",
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                }
                if (idx < activeRecommendations.lastIndex) {
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .height(1.dp)
                            .background(RoutineGrey.copy(alpha = 0.10f)),
                    )
                }
            }
        }

        if (!acknowledged) {
            Text(
                "Acknowledge the incident first to enable dispatch.",
                style = MaterialTheme.typography.labelSmall,
                color = TextMicro,
            )
        }

        Text(
            "Simulated dispatch. No real emergency service is contacted.",
            style = MaterialTheme.typography.labelSmall,
            color = TextMicro,
        )
    }

    // Dispatch confirmation — never one tap
    pending?.let { option ->
        AlertDialog(
            onDismissRequest = { pending = null },
            title = {
                Text(
                    "CONFIRM SIMULATED DISPATCH",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
            },
            text = {
                Text(
                    "Assign ${option.label} to this incident?\n\n${option.reason}\n\n" +
                        "This is a SIMULATED assignment. No real emergency service is contacted.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onDispatch(option.id, option.reason)
                        pending = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = org.disastermesh.sentinel.ui.theme.CriticalRed),
                    shape = RoundedCornerShape(4.dp),
                ) {
                    Text("CONFIRM DISPATCH", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { pending = null }) {
                    Text("Cancel")
                }
            },
        )
    }
}
