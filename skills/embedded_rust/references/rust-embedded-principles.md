# Rust Embedded — In-Depth Reference

A principle-level guide for writing safe, clean, and resource-conscious embedded Rust (`no_std`, bare-metal, `cortex-m`, `embassy`, `RTIC`).

---

## Ownership and Borrowing

- Rust's ownership rules apply exactly the same in `no_std`.
- One owner, many immutable borrows (`&T`), or one mutable borrow (`&mut T`).
- Keep driver structs small and parameterize with lifetimes when they hold references.
- Avoid `static mut`; prefer `static` with a `Mutex`/`CriticalSection` or atomics.
- Interior mutability (`RefCell`, `Mutex`, `UnsafeCell`) must match the actual concurrency model.
- Do not fight the borrow checker with raw pointers unless absolutely necessary.

## no_std and Core/Alloc

- Use `#![no_std]` for all firmware.
- `core` is always available; `alloc` requires a global allocator and a `#[global_allocator]`.
- Prefer `heapless` or fixed arrays over `Vec`/`Box` for predictable memory.
- Define a `#[cfg(not(test))]` panic handler; do not panic in drivers.
- Use `core::fmt::Write` only if needed; `defmt` is far cheaper.

## Unsafe

- `unsafe` is for: FFI, raw pointer dereferences, inline assembly, `transmute`, and union access.
- Every `unsafe` block must have a `// SAFETY:` comment explaining the preconditions.
- Validate all invariants at the call site, not inside the `unsafe` block.
- Wrap `unsafe` in safe APIs with documented contracts.
- Avoid `transmute` between types of different layouts or sizes.
- Do not cast references to raw pointers and back unless the lifetime is clear.

## Concurrency

- `Send` and `Sync` are the type-system guards for sharing.
- Shared mutable state must use `critical-section` or atomic types (`AtomicU32`, etc.).
- Never use `std::sync` in `no_std`.
- ISRs and main code must not race; protect all shared statics.
- Avoid `unsafe` preemption unless the priority scheme is fully understood.

## embassy and RTIC

- `embassy` uses async/await; tasks are `static` and run on an executor.
- `RTIC` is a hardware scheduler; resources are protected at compile time by the framework.
- Do not block an async task; use `Timer::after` or `select` instead.
- Keep tasks small and single-purpose, like functions.
- Static `Channel`/`Queue` objects should have clear ownership.

## Tooling

- `cargo clippy --target <triplet>` with `-D warnings` in CI.
- `cargo fmt` for formatting.
- `cargo audit` for dependency vulnerabilities.
- `cargo bloat` for size analysis.
- `probe-rs` or `cargo-embed` for flashing and RTT logging.
- `defmt` for structured, binary logging; avoid `format!` in firmware.

## Common Gotchas

- `println!` and `format!` pull in `std` or large `core::fmt` code; use `defmt`.
- `unwrap()` in drivers becomes a panic; use `?` and `Result` propagation.
- `static mut` is unsound in the presence of concurrency; use `critical-section`.
- Interrupt handlers must not allocate or hold locks for long.
- `Drop` is not guaranteed if the device is reset; do not rely on cleanup.
