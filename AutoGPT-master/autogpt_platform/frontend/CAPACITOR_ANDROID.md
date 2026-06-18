# Capacitor Android App

This folder includes a Capacitor Android shell for the existing AutoGPT web app.
It does not replace the normal Next.js web workflow.

## Development

Android builds require Android Studio with the Android SDK and a modern JDK. If
Gradle reports that `JAVA_HOME` is missing, install Android Studio and point
`JAVA_HOME` at its bundled JDK, for example:

```powershell
$env:JAVA_HOME="C:\Program Files\Android\Android Studio\jbr"
$env:Path="$env:JAVA_HOME\bin;$env:Path"
```

Start the web app as usual:

```powershell
corepack pnpm dev
```

The Android emulator can reach the host machine at `http://10.0.2.2:3000`, which
is the default `CAPACITOR_SERVER_URL` in `capacitor.config.ts`.

For a physical Android phone connected over USB, forward the phone's local port
to the computer's Next.js dev server, then sync Capacitor with `localhost`:

```powershell
adb reverse tcp:3000 tcp:3000
$env:CAPACITOR_SERVER_URL="http://localhost:3000"
corepack pnpm run cap:sync:android
```

For a physical Android phone without USB forwarding, connect the phone and
computer to the same network, then point Capacitor at the computer LAN IP:

```powershell
$env:CAPACITOR_SERVER_URL="http://192.168.1.23:3000"
corepack pnpm run cap:sync:android
corepack pnpm run cap:open:android
```

Replace `192.168.1.23` with the computer's actual LAN IP.

## Commands

```powershell
corepack pnpm run cap:sync:android
corepack pnpm run cap:open:android
corepack pnpm run app:android:dev
```

## Notes

- The existing web commands (`dev`, `build`, `start`) are unchanged.
- The Android app currently loads the running web app through `server.url`.
- Development HTTP traffic is enabled for local emulator and LAN testing.
- iOS packaging requires macOS and Xcode.
