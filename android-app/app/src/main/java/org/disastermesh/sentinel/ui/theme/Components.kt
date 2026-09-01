package org.disastermesh.sentinel.ui.theme

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.domain.Quantity
import org.disastermesh.sentinel.domain.VerificationStatus
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * Shared components — DisasterMesh Sentinel design system.
 *
 * Rules:
 * - Colour is never the only signal. Every badge carries a word.
 * - Every badge exposes a content description for screen readers.
 * - Touch targets ≥ 48dp enforced by Material3.
 * - Spider/Web identity: living web visualization on Relay screen.
 */

// ── Priority display helpers ──────────────────────────────────────────────────

fun PriorityClass.label(): String = when (this) {
    PriorityClass.P0 -> "P0 CRITICAL"
    PriorityClass.P1 -> "P1 URGENT"
    PriorityClass.P2 -> "P2 OPERATIONAL"
    PriorityClass.P3 -> "P3 ROUTINE"
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
    raw != null   -> "Unknown (\"$raw\")"
    else          -> "Unknown"
}

// ── Badges ────────────────────────────────────────────────────────────────────

@Composable
fun PriorityBadge(priority: PriorityClass, modifier: Modifier = Modifier) {
    Badge(text = priority.label(), color = priority.color(), filled = true, modifier = modifier)
}

@Composable
fun VerificationBadge(status: VerificationStatus, modifier: Modifier = Modifier) {
    when (status) {
        VerificationStatus.HUMAN_VERIFIED ->
            Badge("HUMAN VERIFIED", VerifiedGreen, filled = true, modifier = modifier)
        VerificationStatus.AI_CLASSIFIED ->
            Badge("AI SUGGESTION", AiAccent, filled = false, modifier = modifier)
        VerificationStatus.DISPUTED ->
            Badge("DISPUTED", UrgentOrange, filled = false, modifier = modifier)
        VerificationStatus.UNVERIFIED ->
            Badge("UNVERIFIED", RoutineGrey, filled = false, modifier = modifier)
    }
}

@Composable
fun Badge(
    text: String,
    color: Color,
    filled: Boolean,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .background(
                if (filled) color.copy(alpha = 0.16f) else Color.Transparent,
                RoundedCornerShape(2.dp),   // Sharp edges — not pill soup
            )
            .border(1.dp, color.copy(alpha = if (filled) 0.50f else 0.40f), RoundedCornerShape(2.dp))
            .padding(horizontal = Spacing.sm, vertical = 2.dp)
            .semantics { contentDescription = text },
    ) {
        Text(
            text,
            style = MaterialTheme.typography.labelSmall,
            color = color,
            fontWeight = FontWeight.Bold,
        )
    }
}

// ── Network status ────────────────────────────────────────────────────────────

/** Network state: mesh connection indicator. Never louder than the incident beside it. */
@Composable
fun NetworkStatusChip(
    online: Boolean,
    nearbyPeers: Int,
    modifier: Modifier = Modifier,
) {
    val color = if (online) VerifiedGreen else RoutineGrey
    val label = if (online) "ONLINE · $nearbyPeers NEARBY" else "OFFLINE · $nearbyPeers NEARBY"

    Row(
        modifier = modifier
            .background(color.copy(alpha = 0.10f), RoundedCornerShape(2.dp))
            .border(1.dp, color.copy(alpha = 0.35f), RoundedCornerShape(2.dp))
            .padding(horizontal = Spacing.sm, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
    ) {
        // Breathing status dot
        val infiniteTransition = rememberInfiniteTransition(label = "networkPulse")
        val alpha by infiniteTransition.animateFloat(
            initialValue = 1f,
            targetValue = 0.25f,
            animationSpec = infiniteRepeatable(
                animation = tween(1400),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "dotAlpha",
        )
        Box(
            modifier = Modifier
                .size(5.dp)
                .clip(CircleShape)
                .background(color.copy(alpha = alpha)),
        )
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = color,
        )
    }
}

// ── Offline banner ─────────────────────────────────────────────────────────────

@Composable
fun OfflineBanner(queued: Int, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(RoutineGrey.copy(alpha = 0.10f), RoundedCornerShape(4.dp))
            .border(1.dp, RoutineGrey.copy(alpha = 0.20f), RoundedCornerShape(4.dp))
            .padding(Spacing.md),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
    ) {
        Column {
            Text(
                "OFFLINE",
                style = MaterialTheme.typography.labelLarge,
                color = TextDim,
            )
            Text(
                "Your reports are saved on this device and will pass to nearby mesh nodes. " +
                    "$queued bundle${if (queued != 1) "s" else ""} waiting.",
                style = MaterialTheme.typography.bodySmall,
                color = TextDim,
                modifier = Modifier.padding(top = 2.dp),
            )
        }
    }
}

// ── Sync progress ─────────────────────────────────────────────────────────────

@Composable
fun SyncProgressRow(
    label: String,
    transferred: Long,
    total: Long,
    modifier: Modifier = Modifier,
) {
    val fraction = if (total > 0) (transferred.toFloat() / total) else 0f
    Column(modifier.fillMaxWidth().padding(vertical = Spacing.xs)) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, style = MaterialTheme.typography.bodySmall, color = TextDim)
            Text(
                "${(fraction * 100).toInt()}%",
                style = MaterialTheme.typography.labelSmall,
                color = TextDim,
            )
        }
        Spacer(Modifier.height(4.dp))
        LinearProgressIndicator(
            progress = { fraction },
            modifier = Modifier.fillMaxWidth().height(2.dp),
            color = MeshBlue,
            trackColor = MeshBlue.copy(alpha = 0.15f),
        )
    }
}

// ── Sync state chip ────────────────────────────────────────────────────────────

enum class SyncState { LOCAL, QUEUED, SYNCING, SYNCED, FAILED }

@Composable
fun SyncStateChip(state: SyncState, modifier: Modifier = Modifier) {
    val (label, color) = when (state) {
        SyncState.LOCAL   -> "LOCAL" to RoutineGrey
        SyncState.QUEUED  -> "QUEUED" to UrgentOrange
        SyncState.SYNCING -> "SYNCING" to MeshBlue
        SyncState.SYNCED  -> "SYNCED" to VerifiedGreen
        SyncState.FAILED  -> "FAILED" to CriticalRed
    }
    Badge(text = label, color = color, filled = false, modifier = modifier)
}

// ── AI insight card ───────────────────────────────────────────────────────────

/** AI output is always framed as a suggestion, visually and in words. */
@Composable
fun AiInsightCard(
    headline: String,
    explanation: List<String>,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(AiAccent.copy(alpha = 0.08f), RoundedCornerShape(4.dp))
            .border(1.dp, AiAccent.copy(alpha = 0.25f), RoundedCornerShape(4.dp))
            .padding(Spacing.md),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Badge("AI SUGGESTION", AiAccent, filled = false)
            Spacer(Modifier.width(Spacing.sm))
            Text(
                "· human decides",
                style = MaterialTheme.typography.labelSmall,
                color = TextMicro,
            )
        }
        Spacer(Modifier.height(Spacing.sm))
        Text(
            headline,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurface,
        )
        explanation.take(6).forEach { line ->
            Text(
                "· $line",
                style = MaterialTheme.typography.bodySmall,
                color = TextDim,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
        Text(
            "AI proposes · policy decides · human confirms",
            style = MaterialTheme.typography.labelSmall,
            color = AiAccent.copy(alpha = 0.60f),
            modifier = Modifier.padding(top = Spacing.sm),
        )
    }
}

// ── Empty / error states ───────────────────────────────────────────────────────

@Composable
fun EmptyState(message: String, modifier: Modifier = Modifier) {
    Box(
        modifier.fillMaxWidth().heightIn(min = 100.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            message,
            style = MaterialTheme.typography.bodySmall,
            color = TextMicro,
        )
    }
}

@Composable
fun ErrorState(message: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(CriticalRed.copy(alpha = 0.08f), RoundedCornerShape(4.dp))
            .border(1.dp, CriticalRed.copy(alpha = 0.25f), RoundedCornerShape(4.dp))
            .padding(Spacing.md),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
    ) {
        Text("⚠", color = CriticalRed)
        Text(message, style = MaterialTheme.typography.bodySmall, color = CriticalRed)
    }
}

// ── Spider/Web Mini — Canvas-drawn living web ─────────────────────────────────

/**
 * Renders a living spider-web visualization centered on THIS DEVICE,
 * with peer nodes arranged radially around it.
 *
 * State-driven: strand color and opacity reflect actual connection quality.
 * When nearbyPeers == 0, shows isolated node with empty strands.
 */
@Composable
fun SpiderWebMini(
    nearbyPeers: Int,
    isOnline: Boolean,
    modifier: Modifier = Modifier,
    nodeColor: Color = MeshBlue,
    centerLabel: String = "THIS DEVICE",
    webSize: Dp = 200.dp,
) {
    val peerCount = nearbyPeers.coerceIn(0, 8)

    // Breathing animation for active strands
    val infiniteTransition = rememberInfiniteTransition(label = "webPulse")
    val strandPulse by infiniteTransition.animateFloat(
        initialValue = 0.35f,
        targetValue = 0.75f,
        animationSpec = infiniteRepeatable(
            animation = tween(2200),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "strandPulse",
    )

    val activeStrandAlpha = if (isOnline) strandPulse else 0.18f
    val centerNodeColor = if (isOnline) nodeColor else RoutineGrey
    val peerNodeColor = OperationalBlue

    Box(
        modifier = modifier.size(webSize),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(webSize)) {
            val cx = size.width / 2f
            val cy = size.height / 2f
            val outerRadius = size.width * 0.42f
            val innerRadius = size.width * 0.24f
            val nodeRadius = size.width * 0.055f
            val centerNodeRadius = size.width * 0.08f

            // Draw concentric web rings
            drawCircle(
                color = nodeColor.copy(alpha = 0.07f),
                radius = outerRadius,
                style = Stroke(width = 1f, pathEffect = null),
            )
            drawCircle(
                color = nodeColor.copy(alpha = 0.10f),
                radius = innerRadius,
                style = Stroke(width = 0.8f, pathEffect = null),
            )

            // Draw radial strand lines (web spokes) to each peer
            val angleStep = if (peerCount > 0) (2 * PI / peerCount).toFloat() else 0f
            for (i in 0 until peerCount) {
                val angle = i * angleStep - (PI / 2).toFloat()
                val peerX = cx + outerRadius * cos(angle)
                val peerY = cy + outerRadius * sin(angle)

                // Strand from center to peer
                drawLine(
                    color = nodeColor.copy(alpha = activeStrandAlpha),
                    start = Offset(cx, cy),
                    end = Offset(peerX, peerY),
                    strokeWidth = 1.2f,
                    cap = StrokeCap.Round,
                )

                // Inner ring junction dot
                val midX = cx + innerRadius * cos(angle)
                val midY = cy + innerRadius * sin(angle)
                drawCircle(
                    color = nodeColor.copy(alpha = activeStrandAlpha * 0.6f),
                    radius = 2.5f,
                    center = Offset(midX, midY),
                )

                // Peer node circle
                drawCircle(
                    color = peerNodeColor.copy(alpha = 0.80f),
                    radius = nodeRadius,
                    center = Offset(peerX, peerY),
                )
                drawCircle(
                    color = peerNodeColor.copy(alpha = 0.25f),
                    radius = nodeRadius + 4f,
                    center = Offset(peerX, peerY),
                    style = Stroke(width = 1f),
                )
            }

            // Empty strand hints when no peers (radial lines at fixed positions)
            if (peerCount == 0) {
                val emptyAngles = listOf(0f, PI.toFloat() * 0.5f, PI.toFloat(), PI.toFloat() * 1.5f)
                for (angle in emptyAngles) {
                    val endX = cx + outerRadius * cos(angle)
                    val endY = cy + outerRadius * sin(angle)
                    drawLine(
                        color = RoutineGrey.copy(alpha = 0.15f),
                        start = Offset(cx, cy),
                        end = Offset(endX, endY),
                        strokeWidth = 0.8f,
                        cap = StrokeCap.Round,
                    )
                }
            }

            // Center node — THIS DEVICE
            // Halo
            drawCircle(
                color = centerNodeColor.copy(alpha = 0.12f),
                radius = centerNodeRadius + 8f,
                center = Offset(cx, cy),
            )
            // Node body
            drawCircle(
                color = centerNodeColor,
                radius = centerNodeRadius,
                center = Offset(cx, cy),
            )
            // Node ring
            drawCircle(
                color = centerNodeColor.copy(alpha = 0.50f),
                radius = centerNodeRadius + 3f,
                center = Offset(cx, cy),
                style = Stroke(width = 1.5f),
            )
        }

        // Center label — drawn in Compose (not Canvas) for proper text rendering
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(top = (webSize.value * 0.30f).dp),
        ) {
            Text(
                centerLabel,
                style = MaterialTheme.typography.labelSmall,
                color = TextMicro,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

// ── Mesh strand indicator — sync flow bar ─────────────────────────────────────

/**
 * A compact animated mesh-strand indicator: shows data flowing along a horizontal bar.
 * Used to indicate active sync/relay activity without a full web diagram.
 */
@Composable
fun MeshStrandIndicator(
    isActive: Boolean,
    label: String,
    modifier: Modifier = Modifier,
) {
    val infiniteTransition = rememberInfiniteTransition(label = "strandFlow")
    val progress by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200),
            repeatMode = RepeatMode.Restart,
        ),
        label = "strandProgress",
    )

    val activeColor = MeshBlue
    val inactiveColor = RoutineGrey

    Column(modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                label,
                style = MaterialTheme.typography.labelSmall,
                color = if (isActive) TextDim else TextMicro,
            )
            if (isActive) {
                Text(
                    "ACTIVE",
                    style = MaterialTheme.typography.labelSmall,
                    color = activeColor,
                )
            }
        }
        Spacer(Modifier.height(4.dp))
        if (isActive) {
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().height(2.dp),
                color = activeColor,
                trackColor = activeColor.copy(alpha = 0.12f),
            )
        } else {
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(inactiveColor.copy(alpha = 0.15f)),
            )
        }
    }
}

// ── Previews ─────────────────────────────────────────────────────────────────

@Preview(name = "Dark — Priority badges", showBackground = true, backgroundColor = 0xFF050A14)
@Composable
private fun PriorityBadgePreview() {
    SentinelTheme(darkTheme = true) {
        Column(
            Modifier.padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            PriorityClass.entries.forEach { PriorityBadge(it) }
            VerificationBadge(VerificationStatus.AI_CLASSIFIED)
            VerificationBadge(VerificationStatus.HUMAN_VERIFIED)
            NetworkStatusChip(online = true, nearbyPeers = 4)
            NetworkStatusChip(online = false, nearbyPeers = 1)
            SyncStateChip(SyncState.SYNCING)
            SyncStateChip(SyncState.SYNCED)
            SyncStateChip(SyncState.FAILED)
        }
    }
}

@Preview(name = "Dark — Spider Web Mini (4 peers)", showBackground = true, backgroundColor = 0xFF050A14)
@Composable
private fun SpiderWebMiniPreview() {
    SentinelTheme(darkTheme = true) {
        Box(Modifier.padding(Spacing.xl), contentAlignment = Alignment.Center) {
            SpiderWebMini(nearbyPeers = 4, isOnline = true)
        }
    }
}

@Preview(name = "Dark — Spider Web Mini (offline)", showBackground = true, backgroundColor = 0xFF050A14)
@Composable
private fun SpiderWebMiniOfflinePreview() {
    SentinelTheme(darkTheme = true) {
        Box(Modifier.padding(Spacing.xl), contentAlignment = Alignment.Center) {
            SpiderWebMini(nearbyPeers = 0, isOnline = false)
        }
    }
}

@Preview(name = "Dark — Mesh Strand Indicator", showBackground = true, backgroundColor = 0xFF050A14)
@Composable
private fun MeshStrandIndicatorPreview() {
    SentinelTheme(darkTheme = true) {
        Column(Modifier.padding(Spacing.md), verticalArrangement = Arrangement.spacedBy(Spacing.md)) {
            MeshStrandIndicator(isActive = true, label = "Bundle relay active")
            MeshStrandIndicator(isActive = false, label = "No active relay")
        }
    }
}
