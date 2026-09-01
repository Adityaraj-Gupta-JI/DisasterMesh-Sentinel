package org.disastermesh.sentinel.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import org.disastermesh.sentinel.ui.theme.ErrorState
import org.disastermesh.sentinel.ui.theme.NetworkStatusChip
import org.disastermesh.sentinel.ui.theme.Spacing

/**
 * Relay experience.
 *
 * Participation is opt-in and pausable. The screen shows counts and timings only —
 * never the content of what is being carried, because this device cannot read it.
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
        modifier.fillMaxSize().padding(Spacing.md),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Relay mode", style = MaterialTheme.typography.titleLarge)
            NetworkStatusChip(online = false, nearbyPeers = state.nearbyPeers)
        }

        Card(Modifier.fillMaxWidth()) {
            Row(
                Modifier.fillMaxWidth().padding(Spacing.md),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        if (state.enabled) "Relaying is on" else "Relaying is off",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        "Your phone can carry encrypted emergency reports for other " +
                            "people and pass them on. You cannot read what you carry.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                Switch(checked = state.enabled, onCheckedChange = onToggleRelay)
            }
        }

        if (!state.permissionsGranted) {
            ErrorState(
                state.permissionMessage
                    ?: "Bluetooth and nearby-device permissions are needed to relay. " +
                    "Without them this phone can still create its own reports."
            )
            Button(onClick = onRequestPermissions, modifier = Modifier.fillMaxWidth()) {
                Text("Grant permissions")
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(Spacing.md), verticalArrangement = Arrangement.spacedBy(Spacing.sm)) {
                // Metadata only. Nothing here reveals what any report says.
                StatRow("Nearby devices", state.nearbyPeers.toString())
                StatRow("Reports carried", state.storedBundles.toString())
                StatRow("Reports passed on", state.forwardedBundles.toString())
                StatRow("Last transfer", state.lastTransferLabel ?: "none yet")
                StatRow("Battery", "${state.batteryPercent}%")
                StatRow("Free storage", "${state.storageFreeMb} MB")
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(Spacing.md)) {
                Text("What this phone stores", style = MaterialTheme.typography.titleLarge)
                Text(
                    "Encrypted reports from people nearby, kept until they reach a " +
                        "coordinator or expire. Below 20% battery, only urgent reports " +
                        "move. Below 10%, only critical ones.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun StatRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}
