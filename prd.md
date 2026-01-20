# Product Requirements Document (PRD)

**Project:** Couch Control - Lightweight Remote Desktop  
**Type:** Greenfield Full-Stack Application  
**Version:** 3.0 (WebSocket Real-time Streaming)  
**Date:** January 20, 2026  
**Author:** Product Manager  
**Language:** Python 3.10+

---

## 1. Executive Summary

### 1.1 Problem Statement
As a developer working from home on Linux (Mint/KDE/etc.), you frequently need to interact with your desktop PC (clicking buttons, typing prompts) while building apps with AI agents like Claude Code and Gemini. Currently, when you're in bed or away from your desk, you must physically return to your PC to perform these simple interactions, which disrupts your workflow and comfort.

### 1.2 Solution Overview
An **ultra-lightweight**, on-demand web-based remote desktop viewer that:
- **Uses minimal RAM** (target: < 50MB active, ~0MB idle)
- **No conflicts with KDE/GNOME/etc.** (uses standard X11/D-Bus interfaces)
- Runs locally on your private network (no internet bandwidth waste)
- Starts only when needed (not always broadcasting)
- Allows viewing your desktop screen via any device on the same network
- Enables basic remote control (mouse clicks, keyboard input)
- **True bidirectional real-time communication** via WebSocket

### 1.3 Key Design Decisions (REVISED v3.0 - WebSocket)

| Original Approach | Problem | New Approach |
|-------------------|---------|--------------|
| MJPEG over HTTP | Mobile browsers fail to load, no bidirectional | **WebSocket + Binary Frames** - True real-time |
| Separate /stream and /input endpoints | Two connections, overhead | **Single WebSocket** - bidirectional on one connection |
| HTTP polling for control | Latency, overhead | **WebSocket messages** - instant input response |
| PIL/Pillow encoding | Creates new image objects | **Direct JPEG compression** with mss raw bytes |
| Multiple Python processes | RAM multiplication | **Single async process** with asyncio |
| Always-on frame capture | CPU waste | **On-demand capture** - only when clients connected |

### 1.4 Success Metrics
- Screen sharing accessible within **2 seconds** of service start
- **RAM usage < 50MB** during active streaming
- **RAM usage ~0MB** when stopped (process not running)
- Zero internet bandwidth usage (local network only)
- **No conflicts with KDE Plasma, GNOME, or other DEs**
- Works reliably on phone and other local devices

---

## 2. User Stories & Use Cases

### 2.1 Primary User Stories

**US-1: Quick Service Start**  
As a lazy developer in bed, I want to quickly start the screen sharing service from my phone so I can access my desktop without getting up.

**US-2: View Desktop Screen**  
As a remote user, I want to view my desktop screen in real-time from my phone's browser so I can see what's happening on my PC.

**US-3: Click Buttons Remotely**  
As a developer working with AI agents, I want to click "Allow" buttons and UI elements remotely so I can approve prompts without being at my desk.

**US-4: Type Text Remotely**  
As a remote user, I want to type prompts and commands from my phone so I can continue working with AI agents.

**US-5: Stop Service When Done**  
As a privacy-conscious user, I want to easily stop the screen sharing service when I'm done so my screen isn't always being broadcast.

### 2.2 Use Case Scenarios

**Scenario A: Bedtime AI Development**
1. You're in bed with your phone
2. Claude Code on desktop needs an approval button clicked
3. You open browser: `http://192.168.1.x:8080`
4. Desktop screen appears immediately (MJPEG stream)
5. You tap the approval button on the screen
6. Stop when done (or auto-timeout)

**Scenario B: Quick Prompt Entry**
1. Gemini requests additional input
2. You start the service from anywhere in your home
3. Type the prompt using your phone's keyboard
4. Submit and stop the service

---

## 3. Technical Requirements (REVISED FOR LOW RAM)

### 3.1 Functional Requirements

#### 3.1.1 Service Control
- **FR-1:** Service must start/stop on demand via CLI (`couch-control start/stop`)
- **FR-2:** Service status must be visible (`couch-control status`)
- **FR-3:** Service must auto-stop after configurable timeout (default: 30 minutes)
- **FR-4:** Service must start within **2 seconds**

#### 3.1.2 Screen Sharing
- **FR-5:** Share entire desktop screen (primary monitor)
- **FR-6:** Support adjustable quality levels (JPEG quality 20-80)
- **FR-7:** Target **10-20 FPS** for responsive interaction (adjustable)
- **FR-8:** Automatically scale to reduce bandwidth (default: 50% scale)

#### 3.1.3 Remote Control
- **FR-9:** Support mouse click events (left-click, right-click, middle-click)
- **FR-10:** Support mouse movement and positioning
- **FR-11:** Support keyboard input via virtual keyboard
- **FR-12:** Map touch gestures to mouse actions on mobile

#### 3.1.4 Network & Security
- **FR-13:** Operate exclusively on local network
- **FR-14:** No external internet traffic when sharing screen
- **FR-15:** Optional basic authentication (PIN)
- **FR-16:** Bind to specific interface (not 0.0.0.0 by default)

### 3.2 Non-Functional Requirements (REVISED)

#### 3.2.1 Performance - CRITICAL
- **NFR-1:** RAM usage **< 50MB** when actively streaming
- **NFR-2:** RAM usage **~0MB** when service stopped (no daemon)
- **NFR-3:** CPU usage < 10% when idle (no clients)
- **NFR-4:** CPU usage < 25% when streaming at 15 FPS
- **NFR-5:** Latency < 200ms for click/keyboard actions
- **NFR-6:** Bandwidth < 2 Mbps on local network (MJPEG at 50% quality)

#### 3.2.2 Compatibility - NO CONFLICTS
- **NFR-7:** Must work alongside KDE Plasma without conflicts
- **NFR-8:** Must work alongside GNOME without conflicts
- **NFR-9:** No interference with compositor (KWin, Mutter, etc.)
- **NFR-10:** No interference with screen recording tools
- **NFR-11:** Works on X11 (primary) with Wayland fallback

#### 3.2.3 Usability
- **NFR-12:** Mobile web interface must be responsive and touch-friendly
- **NFR-13:** No installation required on client devices (phone)
- **NFR-14:** Works on all modern mobile browsers (Chrome, Firefox, Safari)

---

## 4. System Architecture (REVISED - WebSocket Real-time)

### 4.1 Protocol Selection: WebSocket + Binary Frames

**Why WebSocket (not MJPEG or WebRTC)?**

| Feature | MJPEG/HTTP | WebRTC | **WebSocket** |
|---------|-----------|--------|---------------|
| Bidirectional | ❌ (separate POST) | ✅ | **✅ (single connection)** |
| Mobile Support | ⚠️ (fails on some) | ✅ | **✅ (universal)** |
| RAM Usage | ~30-50MB | ~100MB+ | **~30-50MB** |
| Real-time Input | ❌ (HTTP latency) | ✅ | **✅ (instant)** |
| Complexity | Low | High | **Low-Medium** |
| Works with Canvas | ❌ | ✅ | **✅** |

**WebSocket Binary Streaming**: Send JPEG frames as binary WebSocket messages. Client renders on Canvas. Input events sent on same connection instantly.

### 4.2 Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                    COUCH CONTROL SERVER                      │
│                     (Single Python Process)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Screen     │    │  WebSocket   │    │    Input     │  │
│  │   Capture    │───▶│   Server     │◀───│   Handler    │  │
│  │   (mss)      │    │ (websockets) │    │  (xdotool)   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                    ▲          │
│         │                   │                    │          │
│         ▼                   ▼                    │          │
│  ┌──────────────┐    ┌──────────────┐           │          │
│  │    JPEG      │    │   Binary     │           │          │
│  │   Encoder    │───▶│   Frames     │           │          │
│  │  (Pillow)    │    │   via WS     │           │          │
│  └──────────────┘    └──────────────┘           │          │
│                             │                    │          │
└─────────────────────────────│────────────────────│──────────┘
                              │                    │
                              ▼                    │
                    ┌──────────────────┐          │
                    │   Phone Browser   │──────────┘
                    │   (Any Device)    │  JSON input via WS
                    │   <canvas>        │
                    └──────────────────┘
```

### 4.3 Technology Stack (FINAL - WebSocket)

#### Backend (Python 3.10+)
```
couch_control/
├── __init__.py
├── server.py          # WebSocket server + HTTP static files
├── capture.py         # mss screen capture + JPEG encoding
├── input_handler.py   # xdotool subprocess for mouse/keyboard
├── config.py          # YAML config loader
└── cli.py             # CLI entry point
```

| Component | Library | Why This Choice |
|-----------|---------|-----------------|
| WebSocket Server | **websockets** | Pure Python, async, lightweight, reliable |
| HTTP Static Files | **aiohttp** | Serve index.html and static files |
| Screen Capture | **mss** | Fastest Python screen capture, direct memory access |
| JPEG Encoding | **Pillow** | Reliable, good quality, acceptable speed |
| Input Control | **xdotool** (subprocess) | Zero Python overhead, battle-tested |
| Config | **PyYAML** | Simple, lightweight |

#### Frontend (Vanilla HTML/CSS/JS)
```
static/
├── index.html         # Single page, minimal
├── style.css          # Mobile-first CSS
└── app.js             # Touch handling, keyboard input
```

**No frameworks needed** - vanilla JS is lighter and faster for this simple use case.

### 4.4 Data Flow (WebSocket Bidirectional)

```
CONNECTION:
1. Browser connects to ws://host:8080/ws
2. Server adds client to connected set
3. Server starts frame loop for this client

SCREEN STREAMING (server → client, every 33-100ms based on FPS):
1. mss.grab(monitor) → Raw BGRA bytes
2. PIL.Image.frombytes() → JPEG bytes
3. websocket.send(jpeg_bytes) → Binary frame to client
4. Client receives ArrayBuffer → Blob → Image → Canvas

INPUT HANDLING (client → server, on each event):
1. Browser sends JSON: {"type": "click", "x": 0.5, "y": 0.3}
2. Server receives via websocket.recv()
3. Server calls xdotool subprocess
4. Input applied instantly (no round-trip needed)
```

### 4.5 Memory Optimization Details

| Technique | RAM Saved |
|-----------|-----------|
| No PIL Image objects (use raw bytes) | ~20MB |
| No WebSocket frame buffering | ~15MB |
| Single process (no multiprocessing) | ~30MB |
| Stream directly (no intermediate storage) | ~10MB |
| Lazy imports (only load when needed) | ~5MB |

---

## 5. API Specification

### 5.1 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve web client (index.html) |
| GET | `/stream` | MJPEG video stream |
| POST | `/input` | Receive mouse/keyboard events |
| GET | `/status` | Server status JSON |
| POST | `/settings` | Update quality/FPS |

### 5.2 MJPEG Stream Format

```http
GET /stream HTTP/1.1
Host: 192.168.1.100:8080

HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace; boundary=frame
Cache-Control: no-cache

--frame
Content-Type: image/jpeg

<JPEG binary data>
--frame
Content-Type: image/jpeg

<JPEG binary data>
...
```

### 5.3 Input Event Format

```json
POST /input
{
  "type": "click",      // click, move, keydown, keyup, scroll
  "x": 0.5,             // Normalized 0-1 (relative to screen)
  "y": 0.3,
  "button": 1,          // 1=left, 2=middle, 3=right
  "key": null           // For keyboard events
}
```

---

## 6. User Interface

### 6.1 Mobile Web Client

```html
<!-- Minimal UI - fits in one screen -->
<div id="app">
  <!-- MJPEG stream - native browser handling -->
  <img id="screen" src="/stream" />
  
  <!-- Floating controls -->
  <div id="controls">
    <button id="keyboard-btn">⌨️</button>
    <select id="quality">
      <option value="30">Low</option>
      <option value="50" selected>Medium</option>
      <option value="70">High</option>
    </select>
  </div>
  
  <!-- Virtual keyboard (hidden by default) -->
  <input id="keyboard-input" type="text" />
</div>
```

### 6.2 Touch Gestures

| Gesture | Action |
|---------|--------|
| Single tap | Left click |
| Long press (500ms) | Right click |
| Two-finger tap | Middle click |
| Drag | Mouse move |
| Pinch | Zoom (client-side only) |

### 6.3 CLI Interface

```bash
# Start server
couch-control start [--port 8080] [--quality 50] [--fps 15]

# Stop server  
couch-control stop

# Check status
couch-control status

# Show local IP
couch-control ip
```

---

## 7. Configuration

### 7.1 Config File Location

```
~/.config/couch-control/config.yaml
```

### 7.2 Configuration Options

```yaml
# Couch Control Configuration

server:
  port: 8080
  # Bind to local network interface only
  # Use "auto" to detect, or specify IP like "192.168.1.100"
  host: "auto"

capture:
  # JPEG quality (10-95, lower = less bandwidth/RAM)
  quality: 50
  # Target FPS (5-30)
  fps: 15
  # Scale factor (0.25-1.0, lower = less bandwidth/RAM)
  scale: 0.5
  # Monitor index (0 = primary)
  monitor: 0

security:
  # Optional PIN (empty = disabled)
  pin: ""
  # Auto-stop after X minutes of no activity
  timeout_minutes: 30

performance:
  # Use turbojpeg if available (faster, less RAM)
  use_turbojpeg: true
  # Maximum concurrent connections
  max_clients: 3
```

---

## 8. Compatibility & Non-Conflict Guarantees

### 8.1 Why This Won't Conflict with KDE/GNOME

| Component | Couch Control Uses | KDE/GNOME Uses | Conflict? |
|-----------|-------------------|----------------|-----------|
| Screen Capture | mss (direct X11 `XGetImage`) | N/A | **No** |
| Input Injection | xdotool (XTest extension) | N/A | **No** |
| Network Port | 8080 (configurable) | Different ports | **No** |
| D-Bus | Not used | Used | **No** |
| PipeWire | Not used | Used for screen share | **No** |
| Compositor | Not touched | KWin/Mutter | **No** |

### 8.2 X11 vs Wayland

| Feature | X11 | Wayland |
|---------|-----|---------|
| Screen Capture | ✅ mss (XGetImage) | ⚠️ Requires xdg-desktop-portal |
| Input Injection | ✅ xdotool | ⚠️ Limited (ydotool) |
| **Recommendation** | Primary target | Fallback with limitations |

**For KDE Plasma on X11**: Full support, no issues.  
**For KDE Plasma on Wayland**: Screen capture via portal, input may be limited.

---

## 9. Implementation Phases

### Phase 1: Core MJPEG Streaming (MVP)
**Goal:** View desktop screen from phone

**Tasks:**
1. Set up aiohttp server with MJPEG endpoint
2. Implement mss screen capture
3. Add JPEG encoding (turbojpeg with Pillow fallback)
4. Create minimal HTML viewer
5. Add CLI start/stop commands

**Deliverable:** Can view desktop at 15 FPS from phone browser

### Phase 2: Remote Input
**Goal:** Click and type remotely

**Tasks:**
1. Add xdotool integration for mouse
2. Implement coordinate normalization
3. Add keyboard input handling
4. Create touch gesture handlers in JS
5. Add virtual keyboard UI

**Deliverable:** Full remote control working

### Phase 3: Polish
**Goal:** Production ready

**Tasks:**
1. Add PIN authentication
2. Implement auto-timeout
3. Add quality presets
4. Optimize memory usage
5. Add systemd service file
6. Error handling and recovery

**Deliverable:** Ready for daily use

---

## 10. Dependencies

### 10.1 Python Packages

```txt
# requirements.txt
aiohttp>=3.9.0          # Async HTTP server
mss>=9.0.0              # Screen capture
PyYAML>=6.0             # Config file
netifaces>=0.11.0       # Auto-detect local IP

# Optional (faster JPEG encoding)
PyTurboJPEG>=1.7.0      # Requires libturbojpeg

# Fallback for JPEG (if turbojpeg unavailable)
Pillow>=10.0.0
```

### 10.2 System Dependencies

```bash
# Required
sudo apt install xdotool

# Optional (faster JPEG - recommended)
sudo apt install libturbojpeg0

# For Wayland support (optional)
sudo apt install ydotool
```

---

## 11. Testing Requirements

### 11.1 Performance Testing
- [ ] RAM usage < 50MB when streaming
- [ ] RAM usage < 30MB when idle (connected but not moving)
- [ ] CPU usage < 25% at 15 FPS
- [ ] No memory leaks after 1 hour of use

### 11.2 Compatibility Testing
- [ ] Works on KDE Plasma (X11) without conflicts
- [ ] Works on GNOME without conflicts
- [ ] Works on Linux Mint Cinnamon
- [ ] No interference with screen recording (OBS, etc.)

### 11.3 Functional Testing
- [ ] MJPEG stream displays correctly on Chrome mobile
- [ ] MJPEG stream displays correctly on Safari iOS
- [ ] Mouse clicks register at correct position
- [ ] Keyboard input works correctly
- [ ] Auto-timeout stops service

---

## 12. Success Criteria

**The project is successful if:**

1. ✅ RAM usage stays under 50MB during active use
2. ✅ No conflicts with KDE Plasma or other DEs
3. ✅ Stream visible within 2 seconds of opening browser
4. ✅ Clicks are accurate to within 5 pixels
5. ✅ Works on both Android Chrome and iOS Safari
6. ✅ Can run for hours without memory growth

---

## Appendix A: Quick Start

```bash
# Install
pip install -e .
sudo apt install xdotool

# Start
couch-control start

# Open on phone
# http://<your-ip>:8080

# Stop
couch-control stop
```

---

## Appendix B: Memory Comparison

| Solution | Idle RAM | Active RAM | Notes |
|----------|----------|------------|-------|
| VNC (x11vnc) | ~50MB | ~80MB | Always-on daemon |
| NoMachine | ~100MB | ~200MB | Heavy client |
| Rustdesk | ~60MB | ~100MB | Good but overkill |
| **Couch Control** | **0MB** | **~40MB** | On-demand only |

---

**End of Document - Ready for Implementation**

---

## Approval Checklist

Please review and confirm:

- [ ] MJPEG over HTTP approach is acceptable (simpler than WebRTC)
- [ ] X11 as primary target (Wayland support limited) is okay
- [ ] Target RAM < 50MB is acceptable
- [ ] Using xdotool for input is acceptable
- [ ] CLI-only control (no GUI dashboard) is acceptable for v1.0

**Awaiting your approval before implementation begins.**
