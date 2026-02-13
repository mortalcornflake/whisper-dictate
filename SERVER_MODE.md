# Whisper Server Mode - Robustness Design

## Architecture

The app uses **lazy server initialization** with automatic cleanup:
- **Primary**: Cloud API (Groq/OpenAI) - always tried first
- **Fallback**: Local whisper server (persistent) OR CLI (one-shot)
- **Cleanup**: Auto-shutdown after 30min idle + graceful exit on Ctrl+C

## All User Journeys (Tested Scenarios)

### Journey 1: WiFi → No WiFi → WiFi (Most Common)
**Scenario**: User starts on WiFi, goes offline, then reconnects

1. **Start**: Groq mode, no server running
2. **Transcription 1**: Groq API ✅ (success, instant)
3. **WiFi drops**
4. **Transcription 2**: Groq fails → starts server (~5-10sec) → uses server ✅
5. **Transcription 3**: Groq fails → uses existing server ✅ (instant)
6. **WiFi returns**
7. **Transcription 4**: Groq API ✅ (success, server stays idle)
8. **After 30min idle**: Server auto-shuts down, frees 1.5GB RAM

**Result**: ✅ Seamless switching, no manual intervention

---

### Journey 2: Local Mode (Offline First)
**Scenario**: User starts in `BACKEND=local` mode

1. **Start**: Server starts immediately (~5-10sec to load model)
2. **Transcription 1-N**: All use server ✅ (instant after first load)
3. **Ctrl+C exit**: Server shuts down gracefully ✅
4. **Idle 30min**: Server auto-shuts down ✅

**Result**: ✅ Fast local transcription, clean resource management

---

### Journey 3: Server Crashes Mid-Session
**Scenario**: Server process dies unexpectedly (OOM, segfault, etc.)

1. **Server running**, serving requests
2. **Server crashes** (process exits)
3. **Next transcription**: Detects dead process → cleans up → falls back to CLI ✅
4. **Subsequent fallback**: Restarts server automatically ✅

**Result**: ✅ Self-healing, temporary CLI fallback, then server restart

---

### Journey 4: Server Fails to Start
**Scenario**: Port 8080 taken, binary missing, or startup timeout

1. **Groq fails** → attempts to start server
2. **Server startup fails** (timeout/died/missing binary)
3. **Process cleanup**: Kills stuck process if any ✅
4. **Transcription**: Falls back to CLI mode ✅
5. **Next fallback**: Retries server start (might succeed if port freed)

**Result**: ✅ Graceful degradation to CLI, automatic retry

---

### Journey 5: Rapid Transcriptions During Fallback
**Scenario**: Multiple transcriptions while WiFi is flaky

1. **Transcription A**: Groq fails → starts server (takes 5-10sec)
2. **Transcription B**: (during A) Groq fails → sees server starting → waits for lock → uses server when ready ✅
3. **Transcription C**: Groq fails → uses existing server ✅

**Result**: ✅ Thread-safe server startup, no race conditions

---

### Journey 6: Force Quit / Kill -9
**Scenario**: User force-quits the app

1. **App force killed**
2. **Server process**: Becomes orphaned, keeps running
3. **Next app start**: Tries to start server → port conflict → falls back to CLI
4. **Manual cleanup**: User runs `pkill -f whisper-server` or `lsof -ti:8080 | xargs kill`

**Result**: ⚠️ Known limitation - orphaned whisper-server requires manual cleanup
**Mitigation**: Use Ctrl+C for clean exits (documented in README)

> **Note**: Recorder subprocess orphans (separate from whisper-server) are now handled automatically via atexit/SIGTERM handlers and parent-death detection in the recording worker. `restart-dictate.sh` also kills orphaned multiprocessing children as a safety net.

---

## Robustness Features Implemented

### 1. Thread Safety
- ✅ `_whisper_server_lock` protects all server state access
- ✅ Idle checker captures decision under lock, acts outside lock
- ✅ No deadlocks (stop_whisper_server acquires its own lock)

### 2. Process Lifecycle Management
- ✅ Startup: Health check with 30sec timeout
- ✅ Startup failure: Kills stuck processes before cleanup
- ✅ Runtime: Detects dead processes and cleans up
- ✅ Shutdown: Graceful terminate (5sec) → force kill (2sec)
- ✅ Idle: Auto-shutdown after 30min

### 3. Error Handling
- ✅ Server missing: Falls back to CLI mode
- ✅ Server dies: Detects and cleans up automatically
- ✅ Port conflicts: Handled via startup timeout → CLI fallback
- ✅ Network errors: Caught and logged, falls back to CLI
- ✅ Stuck processes: Killed during cleanup

### 4. Resource Management
- ✅ Memory: Auto-cleanup after 30min idle (frees 1.5GB)
- ✅ Port 8080: Released when server stops
- ✅ Temp files: Always cleaned up (finally blocks)
- ✅ Subprocess audio: Terminated gracefully → killed if stuck

### 5. Observability
- ✅ Startup: "🚀 Starting whisper server..."
- ✅ Ready: "✅ Whisper server ready (PID: 1234)"
- ✅ Fallback: "⚠️ Cloud failed, falling back to local..."
- ✅ Idle: "💤 Whisper server idle for 30min - shutting down"
- ✅ Errors: Clear messages with context

## Configuration

### Environment Variables
```bash
WHISPER_SERVER_PORT=8080                    # Default port
WHISPER_SERVER_IDLE_TIMEOUT=1800           # 30 minutes (seconds)
```

### Tuning Recommendations
- **Short sessions** (< 30min): Keep default 1800s timeout
- **Long sessions** (hours): Increase to 7200s (2 hours)
- **Memory constrained**: Decrease to 600s (10 min)
- **Always-on**: Set to very high value (86400 = 24 hours)

## Known Limitations

1. **Orphaned processes**: Force-quit leaves server running (fixable with PID file tracking)
2. **Port conflicts**: Only port 8080 supported (could add auto-port-selection)
3. **Single server**: Can't run multiple instances on same machine (by design)

## Future Improvements (Not Implemented)

- [ ] PID file tracking to kill orphaned servers on next start
- [ ] Auto-select available port if 8080 is taken
- [ ] Metrics: track fallback rate, server uptime, transcription speed
- [ ] Health check endpoint to verify server is actually processing
