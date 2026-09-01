package org.disastermesh.sentinel.ui.screens

import android.net.Uri
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
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
import androidx.compose.ui.graphics.Color
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
import org.disastermesh.sentinel.ui.theme.AiInsightCard
import org.disastermesh.sentinel.ui.theme.CriticalRed
import org.disastermesh.sentinel.ui.theme.EmptyState
import org.disastermesh.sentinel.ui.theme.NetworkStatusChip
import org.disastermesh.sentinel.ui.theme.PriorityBadge
import org.disastermesh.sentinel.ui.theme.RoutineGrey
import org.disastermesh.sentinel.ui.theme.Spacing
import org.disastermesh.sentinel.ui.theme.TextDim
import org.disastermesh.sentinel.ui.theme.TextMicro
import org.disastermesh.sentinel.ui.theme.VerifiedGreen
import org.disastermesh.sentinel.ui.theme.color
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
    onSendSos: () -> Unit = onStartReport,
    imageUrlFor: ((incidentId: String, attachmentId: String) -> String)? = null,
    authHeader: String? = null,
) {
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
                        "DISASTERMESH",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "SENTINEL · REPORTER",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMicro,
                    )
                }
            }
            NetworkStatusChip(state.online, state.nearbyPeers)
        }

        // ── SOS — dominant action, reachable with one thumb ────────────────
        Button(
            onClick = onSendSos,
            modifier = Modifier
                .fillMaxWidth()
                .height(Spacing.emergencyButton),
            colors = ButtonDefaults.buttonColors(
                containerColor = CriticalRed,
                contentColor = Color.White,
            ),
            shape = RoundedCornerShape(4.dp),
        ) {
            Text(
                "SEND SOS",
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.Bold,
            )
        }
        Text(
            "Submits immediately — no form required. Add detail below if time allows.",
            style = MaterialTheme.typography.labelSmall,
            color = TextMicro,
            modifier = Modifier.padding(horizontal = Spacing.xs),
        )

        // ── Secondary actions ─────────────────────────────────────────────────
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            OutlinedButton(
                onClick = onStartReport,
                modifier = Modifier.weight(1f).height(Spacing.touchTarget),
                shape = RoundedCornerShape(4.dp),
            ) {
                Text("Report incident", style = MaterialTheme.typography.labelLarge)
            }
            OutlinedButton(
                onClick = onStartVoiceReport,
                modifier = Modifier.weight(1f).height(Spacing.touchTarget),
                shape = RoundedCornerShape(4.dp),
            ) {
                Text("Voice note", style = MaterialTheme.typography.labelLarge)
            }
        }

        // ── Queue status strip ─────────────────────────────────────────────────
        Row(
            Modifier
                .fillMaxWidth()
                .background(
                    if (state.queued > 0) CriticalRed.copy(alpha = 0.07f)
                    else VerifiedGreen.copy(alpha = 0.07f),
                    RoundedCornerShape(4.dp),
                )
                .border(
                    1.dp,
                    if (state.queued > 0) CriticalRed.copy(alpha = 0.20f)
                    else VerifiedGreen.copy(alpha = 0.18f),
                    RoundedCornerShape(4.dp),
                )
                .padding(horizontal = Spacing.md, vertical = Spacing.sm),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    if (state.queued > 0) "${state.queued} QUEUED" else "ALL SENT",
                    style = MaterialTheme.typography.labelLarge,
                    color = if (state.queued > 0) CriticalRed else VerifiedGreen,
                )
                Text(
                    "${state.acknowledged} acknowledged by coordinator",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMicro,
                )
            }
        }

        // ── My reports ─────────────────────────────────────────────────────────
        if (state.myReports.isNotEmpty()) {
            Text(
                "MY REPORTS (${state.myReports.size})",
                style = MaterialTheme.typography.titleMedium,
                color = TextMicro,
                modifier = Modifier.padding(top = Spacing.xs),
            )
            Column(verticalArrangement = Arrangement.spacedBy(0.dp)) {
                state.myReports.forEach { incident ->
                    IncidentRow(
                        incident = incident,
                        onClick = { onOpenReport(incident.id) },
                        imageUrlFor = imageUrlFor,
                        authHeader = authHeader,
                    )
                }
            }
        } else {
            EmptyState("No reports yet.")
        }
    }
}

/** Dense operational row — priority edge + title + compact metadata + photo. */
@Composable
private fun IncidentRow(
    incident: Incident,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    imageUrlFor: ((incidentId: String, attachmentId: String) -> String)? = null,
    authHeader: String? = null,
) {
    val priorityColor = incident.priorityClass.color()

    Row(
        modifier = modifier
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
                .clip(RoundedCornerShape(2.dp))
                .background(priorityColor),
        )

        Column(Modifier.weight(1f)) {
            // Badge + status
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                PriorityBadge(incident.priorityClass)
            }

            // Incident text — most important
            Text(
                incident.originalText,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                modifier = Modifier.padding(top = 3.dp),
            )

            // Status in plain language
            Text(
                statusMessage(incident.status),
                style = MaterialTheme.typography.labelSmall,
                color = TextDim,
                modifier = Modifier.padding(top = 2.dp),
            )

            // Photo preview if available
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
                        contentDescription = "Report Photo",
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 180.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .padding(top = Spacing.xs),
                    )
                }
            }
        }
    }

    // Separator line
    Box(
        Modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(RoutineGrey.copy(alpha = 0.12f)),
    )
}

/** Plain language, no jargon: the person needs to know if help knows. */
fun statusMessage(status: IncidentStatus): String = when (status) {
    IncidentStatus.DRAFT               -> "Not sent yet."
    IncidentStatus.QUEUED              -> "Saved on this phone. Will send when a device is near."
    IncidentStatus.RELAYED             -> "Passed to a nearby device."
    IncidentStatus.RECEIVED            -> "Delivered to a coordinator."
    IncidentStatus.ACKNOWLEDGED        -> "A coordinator has seen your report."
    IncidentStatus.DISPATCH_REQUESTED,
    IncidentStatus.DISPATCHED          -> "Help has been assigned."
    IncidentStatus.EN_ROUTE            -> "Help is on the way."
    IncidentStatus.ARRIVED             -> "Help has arrived."
    IncidentStatus.RESOLVED            -> "This report is closed."
    IncidentStatus.EXPIRED             -> "This report is old, but still saved."
    IncidentStatus.CANCELLED           -> "You cancelled this report."
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
    initialText: String = "",
    onRecordVoice: (() -> Unit)? = null,
    isRecordingVoice: Boolean = false,
    onPickPhoto: (() -> Unit)? = null,
    photoUri: Uri? = null,
    onRemovePhoto: (() -> Unit)? = null,
) {
    var text by remember { mutableStateOf(initialText) }
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
        // ── Header ─────────────────────────────────────────────────────────────
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    "REPORT EMERGENCY",
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    "All fields optional except the description",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMicro,
                )
            }
            OutlinedButton(
                onClick = onCancel,
                shape = RoundedCornerShape(4.dp),
            ) {
                Text("Cancel", style = MaterialTheme.typography.labelLarge)
            }
        }

        // ── Description ────────────────────────────────────────────────────────
        Text(
            "WHAT IS HAPPENING?",
            style = MaterialTheme.typography.titleMedium,
            color = TextDim,
        )
        OutlinedTextField(
            value = text,
            onValueChange = { text = it },
            modifier = Modifier.fillMaxWidth().height(120.dp),
            placeholder = { Text("Describe the situation, dangers, and immediate needs…") },
            shape = RoundedCornerShape(4.dp),
        )

        // ── Voice note & Photo attachments ─────────────────────────────────────
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            if (onRecordVoice != null) {
                OutlinedButton(
                    onClick = onRecordVoice,
                    modifier = Modifier.weight(1f).height(Spacing.touchTarget),
                    shape = RoundedCornerShape(4.dp),
                    colors = if (isRecordingVoice) {
                        ButtonDefaults.outlinedButtonColors(
                            contentColor = CriticalRed,
                        )
                    } else ButtonDefaults.outlinedButtonColors(),
                ) {
                    Text(
                        if (isRecordingVoice) "■ STOP"
                        else "🎤 Voice note",
                        style = MaterialTheme.typography.labelLarge,
                    )
                }
            }

            if (onPickPhoto != null) {
                OutlinedButton(
                    onClick = onPickPhoto,
                    modifier = Modifier.weight(1f).height(Spacing.touchTarget),
                    shape = RoundedCornerShape(4.dp),
                ) {
                    Text(
                        if (photoUri != null) "📷 Change Photo" else "📷 Attach Photo",
                        style = MaterialTheme.typography.labelLarge,
                    )
                }
            }
        }

        // ── Attached Photo Preview ─────────────────────────────────────────────
        if (photoUri != null) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(4.dp))
                    .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp))
                    .padding(Spacing.sm),
                verticalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Photo attached", style = MaterialTheme.typography.labelLarge, color = VerifiedGreen)
                    if (onRemovePhoto != null) {
                        TextButton(onClick = onRemovePhoto) {
                            Text("Remove", color = CriticalRed, style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
                AsyncImage(
                    model = photoUri,
                    contentDescription = "Selected photo preview",
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 200.dp)
                        .clip(RoundedCornerShape(4.dp)),
                )
            }
        }

        // ── Disaster type ──────────────────────────────────────────────────────
        Text("DISASTER TYPE", style = MaterialTheme.typography.titleMedium, color = TextDim)
        Row(
            Modifier.fillMaxWidth(),
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
                    label = { Text(type.name.replace('_', ' '), style = MaterialTheme.typography.labelSmall) },
                )
            }
        }

        // ── Urgency ────────────────────────────────────────────────────────────
        Text("URGENCY", style = MaterialTheme.typography.titleMedium, color = TextDim)
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
                    label = { Text(urgency.name, style = MaterialTheme.typography.labelSmall) },
                )
            }
        }

        // ── People count ───────────────────────────────────────────────────────
        OutlinedTextField(
            value = peopleText,
            onValueChange = { if (it.all { char -> char.isDigit() }) peopleText = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Number of people affected (optional)") },
            placeholder = { Text("e.g. 2") },
            shape = RoundedCornerShape(4.dp),
        )

        // ── Location ───────────────────────────────────────────────────────────
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
        ) {
            Checkbox(checked = shareLocation, onCheckedChange = { shareLocation = it })
            Spacer(Modifier.width(Spacing.xs))
            Column {
                Text("Share my GPS location", style = MaterialTheme.typography.bodyMedium)
                Text(
                    if (shareLocation) "Responders will see where you are"
                    else "Only an approximate area will be shared",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMicro,
                )
            }
        }

        // ── AI insight ─────────────────────────────────────────────────────────
        when {
            !aiAvailable -> Text(
                "Automatic analysis is offline. Report will queue locally and relay.",
                style = MaterialTheme.typography.bodySmall,
                color = TextDim,
            )
            suggestion != null -> AiInsightCard(suggestion.first, suggestion.second)
        }

        // ── Submit ─────────────────────────────────────────────────────────────
        Button(
            onClick = {
                val pCount = peopleText.toIntOrNull()
                onSubmit(text, listOf(selectedType), selectedUrgency, pCount, shareLocation)
            },
            enabled = text.isNotBlank() && !submitting,
            modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
            shape = RoundedCornerShape(4.dp),
        ) {
            Text(
                if (submitting) "SUBMITTING REPORT…" else "SEND EMERGENCY REPORT",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

@Composable
fun SubmissionConfirmationScreen(
    incident: Incident,
    onAddPhoto: () -> Unit,
    onDone: () -> Unit,
    modifier: Modifier = Modifier,
    imageUrlFor: ((attachmentId: String) -> String)? = null,
    authHeader: String? = null,
) {
    Column(
        modifier.fillMaxSize().padding(Spacing.md),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        Text(
            "REPORT SENT",
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Bold,
        )
        PriorityBadge(incident.priorityClass)
        Text(
            statusMessage(incident.status),
            style = MaterialTheme.typography.bodyLarge,
            color = TextDim,
        )

        // Original text shown back — never a rewritten version
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
                "YOUR WORDS",
                style = MaterialTheme.typography.labelSmall,
                color = TextMicro,
            )
            Spacer(Modifier.height(Spacing.xs))
            Text(incident.originalText, style = MaterialTheme.typography.bodyLarge)
        }

        // Render photo if already attached
        if (imageUrlFor != null && incident.attachmentIds.isNotEmpty()) {
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
                    contentDescription = "Attached photo",
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 240.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp)),
                )
            }
        }

        Text(
            "Classified ${incident.priorityClass.label()}. A photo can follow — your message " +
                "goes first so it is never held up.",
            style = MaterialTheme.typography.bodyMedium,
            color = TextDim,
        )

        OutlinedButton(
            onClick = onAddPhoto,
            modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
            shape = RoundedCornerShape(4.dp),
        ) {
            Text(
                if (incident.attachmentIds.isNotEmpty()) "Add another photo" else "Add a photo",
                style = MaterialTheme.typography.labelLarge,
            )
        }

        Button(
            onClick = onDone,
            modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
            shape = RoundedCornerShape(4.dp),
        ) { Text("DONE", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold) }
    }
}
