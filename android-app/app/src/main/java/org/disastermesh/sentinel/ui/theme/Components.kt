package org.disastermesh.sentinel.ui.theme

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.domain.Quantity
import org.disastermesh.sentinel.domain.VerificationStatus

/**
 * Shared components.
 *
 * Rule applied throughout: colour is never the only signal. Every badge carries a word,
 * and every badge exposes a content description for screen readers.
 */

fun PriorityClass.label(): String = when (this) {
    PriorityClass.P0 -> "P0 Critical"
    PriorityClass.P1 -> "P1 Urgent"
    PriorityClass.P2 -> "P2 Operational"
    PriorityClass.P3 -> "P3 Routine"
}

fun PriorityClass.color(): Color = when (this) {
    PriorityClass.P0 -> CriticalRed
    PriorityClass.P1 -> UrgentOrange
    PriorityClass.P2 -> OperationalBlue
    PriorityClass.P3 -> RoutineGrey
}

/** Never renders an unknown count as zero. */
fun Quantity.display(): String = when {
    value != null -> value.toString()
    raw != null -> "Unknown (\"$raw\")"
    else -> "Unknown"
}

@Composable
fun PriorityBadge(priority: PriorityClass, modifier: Modifier = Modifier) {
    Badge(text = priority.label(), color = priority.color(), filled = true, modifier = modifier)
}

@Composable
fun VerificationBadge(status: VerificationStatus, modifier: Modifier = Modifier) {
    when (status) {
        VerificationStatus.HUMAN_VERIFIED ->
            Badge("Human verified", VerifiedGreen, filled = true, modifier = modifier)
        VerificationStatus.AI_CLASSIFIED ->
            Badge("AI suggestion", AiAccent, filled = false, modifier = modifier)
        VerificationStatus.DISPUTED ->
            Badge("Disputed", UrgentOrange, filled = false, modifier = modifier)
        VerificationStatus.UNVERIFIED ->
            Badge("Unverified", RoutineGrey, filled = false, modifier = modifier)
    }
}

@Composable
fun Badge(text: String, color: Color, filled: Boolean, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .background(
                if (filled) color.copy(alpha = 0.18f) else Color.Transparent,
                RoundedCornerShape(999.dp),
            )
            .border(1.dp, color, RoundedCornerShape(999.dp))
            .padding(horizontal = Spacing.sm, vertical = Spacing.xs)
            .semantics { contentDescription = text },
    ) {
        Text(text, style = MaterialTheme.typography.labelSmall, color = color)
    }
}

/** Network state: visible, but never louder than the incident it sits beside. */
@Composable
fun NetworkStatusChip(online: Boolean, nearbyPeers: Int, modifier: Modifier = Modifier) {
    val text = if (online) "Online · $nearbyPeers nearby" else "Offline · $nearbyPeers nearby"
    Badge(text, if (online) VerifiedGreen else RoutineGrey, filled = false, modifier)
}

@Composable
fun OfflineBanner(queued: Int, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = RoutineGrey.copy(alpha = 0.15f)),
    ) {
        Column(Modifier.padding(Spacing.md)) {
            Text("No internet", style = MaterialTheme.typography.titleLarge)
            Text(
                "Your reports are saved on this phone and will pass to nearby devices. " +
                    "$queued waiting.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
fun SyncProgressRow(label: String, transferred: Long, total: Long, modifier: Modifier = Modifier) {
    val fraction = if (total > 0) (transferred.toFloat() / total) else 0f
    Column(modifier.fillMaxWidth().padding(vertical = Spacing.xs)) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            Text("${(fraction * 100).toInt()}%", style = MaterialTheme.typography.labelSmall)
        }
        LinearProgressIndicator(
            progress = { fraction },
            modifier = Modifier.fillMaxWidth().padding(top = Spacing.xs),
        )
    }
}

/** AI output is always framed as a suggestion, visually and in words. */
@Composable
fun AiInsightCard(
    headline: String,
    explanation: List<String>,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = AiAccent.copy(alpha = 0.10f)),
    ) {
        Column(Modifier.padding(Spacing.md)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Badge("AI suggestion", AiAccent, filled = false)
                Text(
                    "  a human decides",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                headline,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = Spacing.sm),
            )
            explanation.take(6).forEach { line ->
                Text("• $line", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
fun EmptyState(message: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().heightIn(min = 120.dp), contentAlignment = Alignment.Center) {
        Text(message, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
fun ErrorState(message: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.error.copy(alpha = 0.12f)
        ),
    ) {
        Text(message, Modifier.padding(Spacing.md), style = MaterialTheme.typography.bodyMedium)
    }
}

@Preview(name = "Priority badges")
@Composable
private fun PriorityBadgePreview() {
    SentinelTheme {
        Column(
            Modifier.padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            PriorityClass.entries.forEach { PriorityBadge(it) }
            VerificationBadge(VerificationStatus.AI_CLASSIFIED)
            VerificationBadge(VerificationStatus.HUMAN_VERIFIED)
            NetworkStatusChip(online = false, nearbyPeers = 3)
            Box(Modifier.size(Spacing.touchTarget))
        }
    }
}
