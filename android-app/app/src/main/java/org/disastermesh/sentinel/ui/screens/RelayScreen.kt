package org.disastermesh.sentinel.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.disastermesh.sentinel.R
import org.disastermesh.sentinel.ui.theme.ErrorState
import org.disastermesh.sentinel.ui.theme.MeshBlue
import org.disastermesh.sentinel.ui.theme.MeshStrandIndicator
import org.disastermesh.sentinel.ui.theme.NetworkStatusChip
import org.disastermesh.sentinel.ui.theme.RoutineGrey
import org.disastermesh.sentinel.ui.theme.Spacing
import org.disastermesh.sentinel.ui.theme.SpiderWebMini
import org.disastermesh.sentinel.ui.theme.SyncProgressRow
import org.disastermesh.sentinel.ui.theme.TextDim
import org.disastermesh.sentinel.ui.theme.TextMicro
import org.disastermesh.sentinel.ui.theme.UrgentOrange
import org.disastermesh.sentinel.ui.theme.VerifiedGreen

/**
 * Relay experience.
 *
 * Participation is opt-in and pausable. The screen shows counts and timings only —
 * never the content of what is being carried, because this device cannot read it.
 *
 * Spider/Web identity: living web visualization centered on THIS DEVICE,
 * with nearby peer nodes arranged radially around it.
 */

data class RelayState(
    val enabled: Boolean = false,
    val nearbyPeers: Int = 0,
    val storedBundles: Int = 0,
    val forwardedBundles: Int = 0,
    val lastTransferLabel: String? = null,
    val batteryPercent: Int = 100,
    val storageFreeMb: Long = 0,
    val permissionsGranted: Boolean = true,
    val permissionMessage: String? = null,
)

@Composable
fun RelayScreen(
    state: RelayState,
    onToggleRelay: (Boolean) -> Unit,
    onRequestPermissions: () -> Unit,
    modifier: Modifier = Modifier,
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
                        "RELAY MODE",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "THIS DEVICE · ${state.nearbyPeers} PEER${if (state.nearbyPeers != 1) "S" else ""} NEARBY",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMicro,
                    )
                }
            }
            NetworkStatusChip(online = state.enabled, nearbyPeers = state.nearbyPeers)
        }

        // ── SPIDER/WEB VISUALIZATION — living web centered on this device ───
        Box(
            Modifier.fillMaxWidth(),
            contentAlignment = Alignment.Center,
        ) {
            SpiderWebMini(
                nearbyPeers = state.nearbyPeers,
                isOnline = state.enabled,
                nodeColor = if (state.enabled) MeshBlue else RoutineGrey,
                centerLabel = "THIS DEVICE",
                webSize = 220.dp,
            )
        }

        // ── Toggle control ─────────────────────────────────────────────────────
        Row(
            Modifier
                .fillMaxWidth()
                .background(
                    if (state.enabled) VerifiedGreen.copy(alpha = 0.07f)
                    else MaterialTheme.colorScheme.surfaceVariant,
                    RoundedCornerShape(4.dp),
                )
                .border(
                    1.dp,
                    if (state.enabled) VerifiedGreen.copy(alpha = 0.22f)
                    else MaterialTheme.colorScheme.outlineVariant,
                    RoundedCornerShape(4.dp),
                )
                .padding(Spacing.md),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    if (state.enabled) "RELAYING — ACTIVE" else "RELAYING — PAUSED",
                    style = MaterialTheme.typography.titleMedium,
                    color = if (state.enabled) VerifiedGreen else TextDim,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(3.dp))
                Text(
                    "Your phone carries encrypted emergency reports for people nearby " +
                        "and passes them on. You cannot read what you carry.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextDim,
                )
            }
            Switch(
                checked = state.enabled,
                onCheckedChange = onToggleRelay,
            )
        }

        // ── Permissions error ─────────────────────────────────────────────────
        if (!state.permissionsGranted) {
            ErrorState(
                state.permissionMessage
                    ?: "Bluetooth and nearby-device permissions are needed to relay. " +
                    "Without them this phone can still create its own reports.",
            )
            Button(
                onClick = onRequestPermissions,
                modifier = Modifier.fillMaxWidth().height(Spacing.touchTarget),
                shape = RoundedCornerShape(4.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = UrgentOrange,
                ),
            ) {
                Text(
                    "GRANT PERMISSIONS",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        // ── Mesh strand indicator — relay activity ────────────────────────────
        MeshStrandIndicator(
            isActive = state.enabled && state.storedBundles > 0,
            label = if (state.storedBundles > 0)
                "Carrying ${state.storedBundles} bundle${if (state.storedBundles != 1) "s" else ""}"
            else "No bundles queued",
        )

        // ── Stats table ────────────────────────────────────────────────────────
        Column(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(4.dp))
                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(4.dp))
                .padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            Text(
                "MESH TELEMETRY",
                style = MaterialTheme.typography.titleMedium,
                color = TextMicro,
            )
            Spacer(Modifier.height(Spacing.xs))
            // Metadata only — no content of reports is shown
            StatRow("Nearby devices",    state.nearbyPeers.toString())
            StatRow("Reports carried",   state.storedBundles.toString())
            StatRow("Reports passed on", state.forwardedBundles.toString())
            StatRow("Last transfer",     state.lastTransferLabel ?: "none yet")
            StatRow("Battery",           "${state.batteryPercent}%")
            StatRow("Free storage",      "${state.storageFreeMb} MB")
        }

        // ── Battery-based relay priority note ────────────────────────────────
        Text(
            "Below 20% battery, only urgent reports relay. " +
                "Below 10%, only critical ones move.",
            style = MaterialTheme.typography.bodySmall,
            color = TextMicro,
        )

        // ── Storage progress ──────────────────────────────────────────────────
        if (state.storedBundles > 0) {
            SyncProgressRow(
                label = "Bundle capacity",
                transferred = state.storedBundles.toLong(),
                total = maxOf(state.storedBundles.toLong() + 10L, 1L),
            )
        }
    }
}

@Composable
private fun StatRow(label: String, value: String) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = TextDim,
        )
        Text(
            value,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.SemiBold,
        )
    }
    Box(
        Modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(RoutineGrey.copy(alpha = 0.10f)),
    )
}
