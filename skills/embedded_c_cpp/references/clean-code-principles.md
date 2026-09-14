# Clean Code — In-Depth Reference

A principle-level distillation of *Clean Code: A Handbook of Agile Software Craftsmanship* by Robert C. Martin. This reference is the deep-dive companion to the `embedded_c_cpp` skill. It is organized chapter-by-chapter so the model can load the relevant section before producing or reviewing C/C++ firmware code.

> **Note:** These are paraphrased rules, not the book text. For full examples and prose, consult the local source `Clean Code.md`.

---

## 1. What Is Clean Code?

Clean code is the opposite of a mess. It reads like well-written prose, has straightforward logic, minimal dependencies, and is focused. It is cared for by its authors.

- **There will always be code.** Higher-level tools still generate or rely on code.
- **Bad code slows everyone down.** The cost of a mess is a nonlinear increase in time, risk, and bugs.
- **Attitude matters.** Clean code is a craft, not a side effect. Own the code you write.
- **The Boy Scout Rule:** Leave the codebase cleaner than you found it. Every check-in should be a small improvement.
- **We are authors.** Code is written once and read many times; optimize for the reader.

---

## 2. Meaningful Names

Names are one of the most powerful forms of documentation. They should answer all the big questions.

### Rules
- **Use intention-revealing names.** `elapsedTimeInDays` is better than `d`.
- **Avoid disinformation.** Do not use names that mean one thing in another domain (`hp`, `aix`, `sc`).
- **Make meaningful distinctions.** `accountData` vs `accountInfo` is not a distinction; `customer` vs `customerObject` is noise.
- **Use pronounceable names.** If you cannot say it in a conversation, it is not a good name.
- **Use searchable names.** Single-letter names and numeric constants are hard to grep.
- **Avoid encodings.** Do not use Hungarian notation, member prefixes (`m_`), or type prefixes.
- **Avoid mental mapping.** A name should not require the reader to translate it.
- **Class names** are noun phrases: `Customer`, `WikiPage`.
- **Method names** are verb phrases: `postPayment`, `deletePage`, `save`.
- **Do not be cute.** Wit is not clarity.
- **Pick one word per concept.** One and only one name for one idea (`fetch`, `get`, `retrieve` are not interchangeable).
- **Do not pun.** Use the same word for the same concept; do not reuse it for different ones.
- **Use solution-domain names** for lower-level code and **problem-domain names** for higher-level business logic.
- **Add meaningful context** when a name is ambiguous by surrounding code or a better enclosing structure.
- **Do not add gratuitous context.** Short names are better than long names that add no information.

---

## 3. Functions

Functions are the primary unit of clean code. They should be small, focused, and readable top-to-bottom.

### Rules
- **Functions should be small.** Ideally 4–10 lines, never more than a screenful.
- **Blocks should be one or two lines.** Indent levels should not be deep.
- **Functions should do one thing.** They should do it well and do it only.
- **One level of abstraction per function.** Mixing high-level policy with bit-twiddling is confusing.
- **Read code from top to bottom** (the Stepdown Rule). Each function calls functions at the next level of abstraction.
- **Use descriptive names.** A long, descriptive name is better than a short, misleading one.
- **Prefer few arguments.** 0–2 is ideal; 3 should be rare; more than 3 is exceptional.
- **Avoid flag arguments.** `render(true)` is two functions in one.
- **Avoid dyadic and triadic functions** unless the arguments form a natural pair or triple.
- **Pass argument objects** or structs when many values are needed.
- **Do not use output arguments.** `outputTo` is awkward and surprising.
- **Command Query Separation.** A function should either do something or answer something, not both.
- **Have no side effects.** A function that does something it does not advertise is dangerous.
- **Prefer exceptions to returning error codes.** Error codes clutter the caller.
- **Extract try/catch blocks.** The try/catch body is one thing and should have its own function.
- **Do not repeat yourself (DRY).** Duplication is the root of many bugs.
- **Structured programming:** one entry, one exit is a guideline, not a religion; early returns often improve clarity.

---

## 4. Comments

Comments are a failure to express ourselves in code. They are necessary sometimes, but never as a substitute for clean code.

### Good Comments
- **Legal comments** (copyright, license) are acceptable.
- **Informative comments** can clarify intent when code cannot.
- **Explanation of intent** when the code itself cannot.
- **Clarification** of a non-obvious standard or algorithm.
- **Warning of consequences** such as "takes a long time to run."
- **TODO comments** with an owner or ticket number.
- **Amplification** to emphasize the importance of something that looks unimportant.

### Bad Comments
- **Mumbling, redundant, or misleading comments.**
- **Mandated comments** that add noise to every function or file.
- **Journal comments** (change logs) in the file — use version control.
- **Noise, position markers, and closing brace comments.**
- **Attribution and bylines** — use version control.
- **Commented-out code** — delete it.
- **HTML in comments.**
- **Nonlocal or too-much information.** Comments should be next to the code they describe.
- **Inobvious connection** between a comment and the code.
- **Function headers** for small, well-named functions.

---

## 5. Formatting

Formatting is communication. Consistency is more important than any single rule.

### Vertical Formatting
- **Source files should be short.** Most files fit on a screen or a few.
- **The newspaper metaphor:** the top of the file should be a headline; details below.
- **Vertical openness** separates concepts; **vertical density** keeps related lines together.
- **Vertical distance:** declarations should be close to use; instance variables together; callers and callees close.
- **Vertical ordering:** high-level concepts first, details later.

### Horizontal Formatting
- **Short lines.** Lines should not need side-scrolling.
- **Horizontal openness and density:** spaces around assignment, no spaces inside parentheses.
- **Do not align horizontally.** It creates artificial coupling and churn in diffs.
- **Indentation** shows structure; keep it consistent.

---

## 6. Objects and Data Structures

Keep data and the operations that operate on it together, or expose the data and keep nothing hidden — but do not do both.

### Rules
- **Data abstraction.** Expose interfaces, not implementation.
- **Data/object anti-symmetry.** Objects hide data and expose behavior; data structures expose data and have no behavior.
- **The Law of Demeter.** A function should only call methods on:
  - itself
  - arguments it receives
  - objects it creates
  - its own fields
- **Avoid train wrecks.** `context.getOptions().getDir().getAbsolutePath()` is a violation.
- **Avoid hybrids.** A class that exposes some data and some behavior is neither a good object nor a good data structure.
- **Hiding structure.** `vehicle.getTank().getPercentFull()` is worse than `vehicle.getFuelPercent()`.
- **Data Transfer Objects (DTOs)** are okay for messages; **Active Records** should not contain business rules.

---

## 7. Error Handling

Error handling is important, but it should not obscure the main logic.

### Rules
- **Use exceptions rather than return codes.** Return codes force the caller to check immediately.
- **Write the try-catch-finally statement first.** It defines the transaction and rollback behavior.
- **Use unchecked exceptions** unless the caller can do something useful with the checked one.
- **Provide context with exceptions.** Include what operation failed and why.
- **Define exception classes in terms of caller's needs**, not the source of the exception.
- **Define the normal flow.** The special case pattern can avoid error-code checks.
- **Do not return null.** Null checks spread through the code base.
- **Do not pass null.** Refuse `NULL` arguments or assert/return early.

---

## 8. Boundaries

Code at the boundaries of systems (third-party libraries, APIs) must be explored and isolated.

### Rules
- **Learning tests are better than free.** Write small tests to learn how a third-party API behaves.
- **Explore boundaries before depending on them.** Read docs and test assumptions.
- **Keep third-party code clean.** Wrap it with a thin adapter that matches your domain.
- **Code that does not yet exist** can be shaped by writing the interface you wish it had.
- **Clean boundaries** mean the rest of the code does not know the messy details of a vendor API.

---

## 9. Unit Tests

Tests are as important as production code. They must be kept clean.

### Rules
- **The Three Laws of TDD:**
  1. Do not write production code until a failing test exists.
  2. Do not write more of a test than is sufficient to fail.
  3. Do not write more production code than is sufficient to pass.
- **Tests enable the -ilities.** Clean tests make the code maintainable, flexible, and reusable.
- **Keep tests clean.** Smelly, long, copy-pasted tests rot the project as fast as bad code.
- **Domain-specific testing language.** Use builder functions and helper methods to make tests readable.
- **A dual standard** is not an excuse for unreadable tests.
- **One assert per test** is a guideline; one concept per test is the real rule.
- **F.I.R.S.T. tests:**
  - **F**ast
  - **I**ndependent
  - **R**epeatable
  - **S**elf-validating
  - **T**imely

---

## 10. Classes

A class should be small and single-purposed.

### Rules
- **Classes should be small.** Size is measured by responsibility, not lines.
- **The Single Responsibility Principle (SRP):** a class should have one and only one reason to change.
- **Cohesion.** A class should have a small number of instance variables, and each method should use most of them.
- **Maintainability depends on SRP.** Large classes are change magnets.
- **Organize for change.** Depend on abstractions, not concretions.

---

## 11–14. Systems, Emergence, Concurrency, Successive Refinement

These chapters move from single classes to larger design.

- **Separate construction from use.** Use factories and dependency injection.
- **Scale by separation of concerns.** Keep unrelated systems apart.
- **Emergent design.** Clean code plus simple design leads to good architecture.
- **A system should be testable, simple, and expressive.** Emergent design rules: run all tests; no duplication; expresses intent; minimizes classes and methods.
- **Concurrency is hard.** Keep it off to one side; prefer message passing and immutable data when possible; make non-threaded code work first.
- **Refactor in small steps** with tests passing as often as possible.

---

## 15–17. Case Studies and Code Smells

The later chapters are detailed walkthroughs of real code and a catalog of smells/heuristics. The key takeaway is that **clean code is achieved through many tiny refactorings guided by tests.**

Common smells to avoid:
- Rigidity, fragility, immobility, viscosity.
- Needless complexity, needless repetition, opacity, obscurity.
- Large classes, long functions, feature envy, inappropriate intimacy.
- Shotgun surgery, divergent change, parallel inheritance hierarchies.
- Data clumps, primitive obsession, switch statements, temporary fields.

---

## How to Use This Reference

When the user's question or code is about one of these chapters, load the corresponding section above before answering. For extended examples and the full argument behind each rule, read the relevant chapter in the local `Clean Code.md`.
