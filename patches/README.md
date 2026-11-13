# macOS arm64 VirGL/SPICE build inputs

## `macos-virgl-cocoa-gl.patch`

Vendored from the macOS virgl QEMU work by Miles Buckton:

- upstream commit: `c95b8c499ba420d677812a7500c037e058a7ec8a`
- parent (this fork's `master`): `49559567804523cb28cad002aa8e97f444e23ad7`
- source: <https://gitlab.com/milesbuckton/qemu/-/commit/c95b8c499ba420d677812a7500c037e058a7ec8a>

It adds the Cocoa GL scanout/ANGLE EGL path and the virtio-gpu blob support
needed by `-device virtio-gpu-gl-pci` + `-display cocoa,gl=es` on Apple
Silicon. It is applied by `.github/workflows/macos-virgl-spice.yml` before
QEMU's `./configure`.

The workflow builds the QEMU tree at this fork's `master` (the patch parent),
not an arbitrary newer upstream branch, so the patch is reproducible. When
moving the fork to a newer QEMU base, rebase/replace this patch and update the
workflow pin together.

## Build product

The workflow installs the macOS virgl Homebrew tap's keg-only runtime libraries:

- `libangle` (EGL/GLES over Metal)
- `libepoxy-angle`
- `virglrenderer` (VirGL + Venus host path)

and Homebrew's `spice-server` / `spice-protocol`, then builds:

```text
qemu-system-aarch64 + qemu-img
  Cocoa + HVF
  SPICE server + QXL
  virtio-gpu-gl-pci + virglrenderer + Venus
  ANGLE GLES via -display cocoa,gl=es
```

The artifact is bundled with `dylibbundler`, signed ad hoc with the Hypervisor
entitlement, and uploaded as `qemu-macos-arm64-virgl-spice.tar.gz`.
