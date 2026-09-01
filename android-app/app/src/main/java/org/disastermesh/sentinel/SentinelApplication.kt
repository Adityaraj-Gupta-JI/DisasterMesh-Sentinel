package org.disastermesh.sentinel

import android.app.Application
import androidx.room.Room
import org.disastermesh.sentinel.data.SentinelDatabase

/**
 * Application container.
 *
 * A hand-rolled container rather than Hilt: the graph is small, and one readable file
 * beats a dependency plus generated code for a prototype of this size. See ADR-0004.
 */
class SentinelApplication : Application() {

    lateinit var database: SentinelDatabase
        private set

    lateinit var repository: org.disastermesh.sentinel.data.SentinelRepository
        private set

    override fun onCreate() {
        super.onCreate()
        database = Room.databaseBuilder(this, SentinelDatabase::class.java, "sentinel.db")
            .build()
        repository = org.disastermesh.sentinel.data.SentinelRepository(database, this)
    }
}

