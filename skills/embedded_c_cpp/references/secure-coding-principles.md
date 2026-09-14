# Secure Coding in C and C++ — In-Depth Reference

A principle-level distillation of *Secure Coding in C and C++* by Robert C. Seacord. This reference is the deep-dive companion to the `embedded_c_cpp` skill. It is organized chapter-by-chapter so the model can load the relevant section before producing or reviewing secure C/C++ firmware.

> **Note:** These are paraphrased rules, not the book text. For full exploit examples, standards references, and prose, consult the local source `secure coding in c and c++.md`.

---

## 1. Running with Scissors — Foundations

Software security is not an afterthought. Vulnerabilities cost money, time, and reputation. The attacker only needs to find one flaw.

### Core Concepts
- **Security policy:** the rules that protect assets.
- **Security flaws:** weaknesses that violate a security policy.
- **Vulnerabilities:** specific flaws that can be exploited.
- **Exploits:** inputs or actions that take advantage of a vulnerability.
- **Mitigations:** controls that reduce the probability or impact of exploitation.
- **Trust boundaries:** points where untrusted data becomes trusted.

### Key Attitude
- Security is a lifecycle activity: training, requirements, design, implementation, verification, and response.
- The same classes of vulnerabilities appear repeatedly because developers do not understand the root causes.

---

## 2. Strings

Strings are the most common source of C/C++ vulnerabilities. The root cause is almost always a failure to manage length and termination.

### Fundamental Rules
- C strings are null-terminated byte arrays. String length is not stored.
- **Never use `gets()`.** It is impossible to use safely.
- **Avoid `strcpy()`, `strcat()`, and `sprintf()` on untrusted input.** They do not bound writes.
- **Use length-bounded alternatives:** `strncpy`, `strncat`, `snprintf`, or C11 `*_s` functions.
- **Always ensure null termination.** `strncpy` does not guarantee it; `strncpy_s` does when used correctly.
- **Do not trust size values provided by untrusted sources.** Validate against the actual buffer.
- **String truncation can be a vulnerability too.** Decide explicitly whether truncation is an error.
- **Wide strings and UTF-8** add multibyte and encoding complexity. Validate encodings and count code points, not bytes.

### Common Mistakes
- Off-by-one on buffer sizes and null-terminator space.
- Null-termination errors after `strncpy` and `memcpy`.
- Passing user data to a format string (see Chapter 6).
- Returning pointers to local buffers or freed strings.

### Runtime Protection
- Enable stack canaries, FORTIFY_SOURCE, and object-size checking.
- Use non-executable stacks and W^X policies when available.
- Static and dynamic taint analysis can detect unvalidated string uses.

---

## 3. Pointer Subterfuge

Attackers can corrupt data pointers, function pointers, exception frames, and virtual-table pointers to hijack control flow.

### Attack Vectors
- **Function pointers:** overwrite a function pointer with the address of shellcode or a useful gadget.
- **Object pointers:** corrupt an object pointer to read or write arbitrary memory.
- **Virtual pointers (vptrs):** in C++, overwrite a vptr to control dispatch.
- **Longjmp and exception handlers:** corrupt saved state or handler records.
- **Global Offset Table (GOT), `.dtors`, and `atexit`:** overwrite pointers in writable sections that are executed later.

### Mitigations
- **Stack canaries** detect stack-smashing before a return.
- **W^X / DEP:** make the stack and heap non-executable.
- **ASLR** makes it harder to predict target addresses.
- **Encode/decode function pointers** with XOR or canary values so corruption becomes invalid.
- **Use `const` and `readonly` segments** for function pointers that should not change.
- In C++, avoid raw vptr manipulation and keep virtual dispatch interfaces minimal.

---

## 4. Dynamic Memory Management

Heap vulnerabilities are often more subtle than stack ones and harder to find with simple mitigations.

### C Memory Management Rules
- **Always check return values** of `malloc`, `calloc`, `realloc`.
- **Initialize allocated memory.** Use `calloc` or explicit initialization.
- **Dereference only valid, non-null pointers.** Validate before use.
- **Do not reference freed memory.** Set the pointer to `NULL` after `free`.
- **Do not free the same memory twice.**
- **Avoid memory leaks,** especially in long-running firmware and loops.
- **Do not mix allocators.** Whoever allocates should free, with the matching deallocator.
- **Watch for zero-length allocations.** They may return `NULL` or a non-`NULL` value; both are legal but dangerous if not handled.

### C++ Memory Management Rules
- **Match `new` with `delete` and `new[]` with `delete[]`.**
- **Use smart pointers** (`std::unique_ptr`, `std::shared_ptr`) and RAII rather than raw ownership.
- **Do not throw from destructors or deallocation functions.**
- **Use container classes** (`std::vector`, `std::string`) with bounds checking; but remember they can still be misused.

### Heap Corruption Patterns
- Buffer overflows into heap metadata.
- Double-free and writing to freed memory.
- Use-after-free and dangling pointers.
- Uninitialized reads.

### Mitigations
- Use modern allocators (`jemalloc`, OpenBSD) with hardening.
- Run static analysis (e.g., `cppcheck`, Infer) and runtime analysis (Valgrind, ASan).
- Randomize heap layout where possible.
- Minimize manual memory management in firmware; prefer static or pool allocation.

---

## 5. Integer Security

Integer errors are a common source of buffer-overflow, allocation, and logic bugs.

### Rules
- **Understand the ranges** of `char`, `short`, `int`, `long`, `size_t`, `ptrdiff_t`, etc.
- **Unsigned wraparound** is defined but still dangerous; **signed overflow** is undefined behavior.
- **Watch conversions.** Conversions can truncate, sign-extend, or change magnitude silently.
- **Integer promotions** and the **usual arithmetic conversions** can widen or change signedness.
- **Never use signed comparison for lengths and sizes.** Use `size_t` or `unsigned`.
- **Check before arithmetic.** For `a + b` where both are untrusted, ensure the result cannot overflow.
- **Prefer safe integer libraries** or compiler intrinsics when values come from external input.

### Vulnerabilities
- Wraparound leading to a small or negative buffer size.
- Truncation when a large value is assigned to a smaller type.
- Signed/unsigned comparisons causing logic errors.
- Shift overflows and out-of-range shifts.

### Mitigations
- Choose the right type for the domain; use fixed-width types (`stdint.h`).
- Validate ranges before operations.
- Use compiler and runtime checks where available (GCC/Clang `-ftrapv`, etc.).
- Be explicit with casts and document invariants.

---

## 6. Formatted Output

`printf`-family functions are powerful, but a user-controlled format string is an arbitrary read/write primitive.

### Rules
- **Never let user or untrusted data reach the format string.** Always use a constant format string.
- **Do not build format strings from input.** Concatenation is unsafe.
- **Use bounded output functions:** `snprintf`, `vsnprintf`.
- **Validate field widths and sizes** to avoid buffer overflow.
- **Do not use `%n`.** It writes to a pointer supplied by the caller.
- **Check return values** to detect truncation.

### Attack Effects
- Crash the process.
- Read stack or arbitrary memory.
- Write arbitrary memory using `%n` or direct argument access.

### Mitigations
- Compiler format-string warnings (`-Wformat`, `-Wformat-security`).
- Static taint analysis.
- Restrict the number of bytes written.
- Use `iostream` in C++ with explicit formatting, but avoid building format strings from input there too.

---

## 7. Concurrency

Concurrency introduces non-deterministic failures that are hard to reproduce. Most concurrency bugs are data races or improper synchronization.

### Rules
- **Identify shared, mutable state.** Every shared, mutable object is a potential race.
- **Protect every shared, mutable object with the right primitive:** mutex, semaphore, atomic, or condition variable.
- **Do not rely on `volatile` for synchronization.** It does not guarantee atomicity or ordering.
- **Keep critical sections small.** Long locks kill performance and invite deadlocks.
- **Get non-threaded code working first.** Concurrency multiplies bugs.
- **Use immutable data structures** where possible.
- **Avoid blocking operations inside a critical section.**

### Common Bugs
- **Race conditions:** outcome depends on timing.
- **Data races:** unprotected read/write or write/write on shared data.
- **Deadlock:** circular lock dependencies.
- **Prematurely releasing a lock** before the protected operation completes.
- **ABA problem** in lock-free code.

### Embedded Notes
- Use RTOS primitives, not busy-wait loops.
- Never do dynamic allocation in an ISR; use lock-free queues or flags.
- Measure stack headroom; threads have limited stacks.

---

## 8. File I/O

File I/O crosses trust boundaries and is subject to race conditions, permissions, and path attacks.

### Rules
- **Do not trust a path from an untrusted source.**
- **Canonicalize paths** before use and reject paths outside the intended directory.
- **Validate file type** (use `fstat` on an already-open descriptor, not `stat` on a path).
- **Watch for TOCTOU (time of check, time of use).** The file can change between `stat` and `open`.
- **Create files with exclusive, restrictive flags** when possible.
- **Do not use predictable temporary file names.**
- **Manage privileges:** drop to least privilege as soon as possible.

### File System Risks
- Symbolic and hard links.
- Device and special files.
- Shared directories and world-writable paths.
- Canonicalization and equivalence errors.

### Mitigations
- Use safe APIs that are not vulnerable to race conditions (`open` with `O_CREAT | O_EXCL`, `fstat`).
- Validate file attributes after opening.
- Restrict permissions and use separate, non-privileged accounts.

---

## 9. Recommended Practices

Security is a discipline, not a single technique.

### Development Lifecycle
- Plan and track security work.
- Train developers on the common vulnerability classes.
- Capture security requirements, misuse cases, and trust boundaries.
- Design with threat modeling and attack-surface analysis.
- Implement with secure coding standards and static analysis.
- Verify with tests, fuzzing, penetration tests, and code audits.

### Implementation
- Use compiler security features and warnings.
- Run static analysis as part of the build.
- Validate all input; use whitelisting, not blacklisting.
- Defense in depth: layer mitigations.
- Keep the design simple; complexity is the enemy of security.

### Verification
- Static analysis and code audits.
- Penetration testing and fuzz testing.
- Independent security review.
- Attack-surface review before release.

---

## How to Use This Reference

When the user's question or code touches one of these chapters, load the corresponding section above before producing or reviewing code. For exploit examples, standards references, and the full reasoning behind a rule, read the relevant chapter in the local `secure coding in c and c++.md`.
