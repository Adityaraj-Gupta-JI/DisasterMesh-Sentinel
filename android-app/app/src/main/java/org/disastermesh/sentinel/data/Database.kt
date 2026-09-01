package org.disastermesh.sentinel.data

import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

/**
 * Local persistence, mirroring `protocol/dms/store/sqlite.py`.
 *
 * Binary attachments live on disk; only metadata and digests live here. Writes are
 * idempotent, and a lifecycle change commits together with its audit entry.
 */

@Entity(
    tableName = "incidents",
    indices = [
        Index("status"), Index("priorityClass", "priorityScore"), Index("expiresAt"),
    ],
)
data class IncidentEntity(
    @PrimaryKey val id: String,
    val sourceNodeId: String,
    val organizationId: String?,
    val originalText: String,
    val sourceLanguage: String,
    val status: String,
    val priorityClass: String,
    val priorityScore: Int,
    val severity: Int,
    val urgency: String,
    val sensitivity: String,
    val verificationStatus: String,
    val expiresAt: Long?,
    val reportedAt: Long,
    val revision: Int,
    val doc: String,
    val updatedAt: Long,
)

@Entity(tableName = "bundles", indices = [Index("incidentId"), Index("expiresAt")])
data class BundleEntity(
    @PrimaryKey val bundleId: String,
    val incidentId: String,
    val payloadType: String,
    val priorityClass: String,
    val priorityScore: Int,
    val expiresAt: Long,
    val hopCount: Int,
    val wire: ByteArray,
    val receivedFrom: String?,
) {
    override fun equals(other: Any?): Boolean = other is BundleEntity && other.bundleId == bundleId
    override fun hashCode(): Int = bundleId.hashCode()
}

@Entity(tableName = "sync_objects", indices = [Index(value = ["bundleId"], unique = true)])
data class SyncObjectEntity(
    @PrimaryKey val id: String,
    val bundleId: String,
    val incidentId: String,
    val payloadType: String,
    val priorityClass: String,
    val priorityScore: Int,
    val sizeBytes: Int,
    val sensitivity: String,
    val allowedRoles: String,
    val expiresAt: Long?,
    val requiresAck: Boolean,
    val deliveredTo: String,
    val attempts: Int,
)

@Entity(tableName = "attachments", indices = [Index("incidentId")])
data class AttachmentEntity(
    @PrimaryKey val id: String,
    val incidentId: String,
    val kind: String,
    val fileName: String,
    val mimeType: String,
    val sizeBytes: Long,
    val sha256: String,
    val localPath: String?,
    val committed: Boolean,
)

@Entity(tableName = "acknowledgements", indices = [Index(value = ["dedupKey"], unique = true)])
data class AcknowledgementEntity(
    @PrimaryKey val id: String,
    val dedupKey: String,
    val incidentId: String,
    val nodeId: String,
    val actorRole: String,
    val note: String?,
    val createdAt: Long,
)

@Entity(tableName = "event_log", indices = [Index("incidentId")])
data class EventLogEntity(
    @PrimaryKey val id: String,
    val incidentId: String?,
    val actorNodeId: String?,
    val actorRole: String?,
    val action: String,
    val detail: String,
    val prevHash: String?,
    val entryHash: String,
    val createdAt: Long,
)

@Entity(tableName = "transfer_sessions")
data class TransferSessionEntity(
    @PrimaryKey val fileId: String,
    val incidentId: String,
    val attachmentId: String,
    val state: String,
    val manifest: String,
    @ColumnInfo(defaultValue = "[]") val receivedChunks: String,
    val bytesReceived: Long,
    val updatedAt: Long,
)

@Dao
interface IncidentDao {
    /** Idempotent by primary key: a duplicate delivery replaces, never duplicates. */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(incident: IncidentEntity)

    @Query("SELECT * FROM incidents WHERE id = :id")
    suspend fun byId(id: String): IncidentEntity?

    @Query("SELECT revision FROM incidents WHERE id = :id")
    suspend fun revisionOf(id: String): Int?

    /** A stale revision arriving late over the mesh must not overwrite a newer one. */
    @Transaction
    suspend fun upsertIfNewer(incident: IncidentEntity) {
        val current = revisionOf(incident.id)
        if (current == null || incident.revision >= current) upsert(incident)
    }

    @Query("SELECT * FROM incidents ORDER BY priorityClass ASC, priorityScore DESC, reportedAt DESC")
    fun observeQueue(): Flow<List<IncidentEntity>>

    @Query("SELECT * FROM incidents WHERE priorityClass = :priority ORDER BY priorityScore DESC")
    fun observeByPriority(priority: String): Flow<List<IncidentEntity>>

    @Query("SELECT COUNT(*) FROM incidents")
    suspend fun count(): Int
}

@Dao
interface BundleDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(bundle: BundleEntity): Long

    @Query("SELECT EXISTS(SELECT 1 FROM bundles WHERE bundleId = :id)")
    suspend fun exists(id: String): Boolean

    @Query("SELECT * FROM bundles WHERE bundleId = :id")
    suspend fun byId(id: String): BundleEntity?

    @Query("SELECT bundleId FROM bundles")
    suspend fun allIds(): List<String>

    @Query("SELECT bundleId FROM bundles WHERE expiresAt <= :now")
    suspend fun expired(now: Long): List<String>

    @Query("SELECT COUNT(*) FROM bundles")
    fun observeCount(): Flow<Int>
}

@Dao
interface SyncDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: SyncObjectEntity)

    @Query(
        """SELECT * FROM sync_objects
           WHERE (expiresAt IS NULL OR expiresAt > :now)
           ORDER BY priorityClass ASC, priorityScore DESC"""
    )
    suspend fun pending(now: Long): List<SyncObjectEntity>
}

@Dao
interface AcknowledgementDao {
    /** IGNORE, not REPLACE: a repeat acknowledgement is absorbed silently. */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(ack: AcknowledgementEntity): Long

    @Query("SELECT * FROM acknowledgements WHERE incidentId = :incidentId")
    suspend fun forIncident(incidentId: String): List<AcknowledgementEntity>
}

@Dao
interface EventLogDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun append(entry: EventLogEntity)

    @Query("SELECT * FROM event_log WHERE incidentId = :incidentId ORDER BY createdAt")
    fun observeForIncident(incidentId: String): Flow<List<EventLogEntity>>

    @Query("SELECT * FROM event_log ORDER BY createdAt DESC LIMIT :limit")
    suspend fun recent(limit: Int): List<EventLogEntity>
}

@Dao
interface AttachmentDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(attachment: AttachmentEntity)

    @Query("SELECT * FROM attachments WHERE incidentId = :incidentId")
    fun observeForIncident(incidentId: String): Flow<List<AttachmentEntity>>
}

@Database(
    entities = [
        IncidentEntity::class, BundleEntity::class, SyncObjectEntity::class,
        AttachmentEntity::class, AcknowledgementEntity::class, EventLogEntity::class,
        TransferSessionEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class SentinelDatabase : RoomDatabase() {
    abstract fun incidents(): IncidentDao
    abstract fun bundles(): BundleDao
    abstract fun sync(): SyncDao
    abstract fun acknowledgements(): AcknowledgementDao
    abstract fun events(): EventLogDao
    abstract fun attachments(): AttachmentDao

    /**
     * A lifecycle change and its audit entry commit together or not at all: an
     * acknowledged incident with no audit record would be worse than neither.
     */
    @Transaction
    open suspend fun applyTransition(incident: IncidentEntity, entry: EventLogEntity) {
        incidents().upsert(incident)
        events().append(entry)
    }
}
