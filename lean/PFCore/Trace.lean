import PFCore.Event

/-!
# PF-Core traces and trace-level safety
-/

namespace PFCore

/-- Ordered action trace (oldest event nearest `empty`). -/
inductive Trace where
  | empty
  | cons : Trace → Event → Trace
deriving Repr

def TraceSafe : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev => TraceSafe tr ∧ EventSafe ev

def traceSafeD : Trace → Bool
  | Trace.empty => true
  | Trace.cons tr ev => traceSafeD tr && eventSafeD ev

/-- Event membership in a trace (structural equality on `Event`). -/
def EventIn (ev : Event) : Trace → Prop
  | Trace.empty => False
  | Trace.cons tr e => ev = e ∨ EventIn ev tr

def eventInD (ev : Event) (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => false
  | Trace.cons tr' e => decide (ev == e) || eventInD ev tr'

/-- Oldest-first event list for trace `tr` (matches runtime event order). -/
def Trace.events : Trace → List Event
  | Trace.empty => []
  | Trace.cons tr ev => Trace.events tr ++ [ev]

/-- Build a trace from an oldest-first event list (chronological accumulation). -/
def Trace.ofEvents (events : List Event) : Trace :=
  events.foldl (fun tr ev => Trace.cons tr ev) Trace.empty

/-- Chronological concatenation: events of `tr1` followed by events of `tr2`. -/
def Trace.append (tr1 tr2 : Trace) : Trace :=
  match tr2 with
  | Trace.empty => tr1
  | Trace.cons tr' ev => Trace.cons (Trace.append tr1 tr') ev

/--
**Meaning:** `Trace.events` lists events in chronological (oldest-first) order.

**Trusted use:** Compositional trace concatenation and projection lemmas.

**Does not imply:** Hash-chain or replay validity.
-/
theorem trace_events_cons (tr : Trace) (ev : Event) :
    Trace.events (Trace.cons tr ev) = Trace.events tr ++ [ev] := by
  simp [Trace.events]

/-- Helper: left-fold `cons` appends events chronologically onto an existing trace. -/
theorem trace_events_foldl_cons (tr : Trace) (events : List Event) :
    Trace.events (events.foldl (fun t e => Trace.cons t e) tr) =
      Trace.events tr ++ events := by
  induction events generalizing tr with
  | nil => simp [List.foldl]
  | cons e es ih =>
    simp [List.foldl, Trace.events, ih]

/--
**Meaning:** `Trace.ofEvents` preserves chronological (oldest-first) list order.

**Trusted use:** Aligning JSON event arrays with Lean `Trace.events`.

**Does not imply:** Hash-chain or replay validity.
-/
theorem trace_events_ofEvents (events : List Event) :
    Trace.events (Trace.ofEvents events) = events := by
  simp [Trace.ofEvents, trace_events_foldl_cons, Trace.events]

/--
**Meaning:** Building a trace from its event list recovers the original trace.

**Trusted use:** Round-trip between inductive traces and oldest-first event lists.

**Does not imply:** Equality of independently constructed traces beyond event lists.
-/
theorem trace_ofEvents_events (tr : Trace) :
    Trace.ofEvents tr.events = tr := by
  induction tr with
  | empty =>
    simp [Trace.ofEvents, Trace.events]
  | cons tr' ev ih =>
    -- events (cons tr' ev) = events tr' ++ [ev]
    -- ofEvents (xs ++ [ev]) = cons (ofEvents xs) ev
    calc
      Trace.ofEvents (Trace.events (Trace.cons tr' ev))
          = Trace.ofEvents (Trace.events tr' ++ [ev]) := by
              simp [Trace.events]
      _ = (fun t => Trace.cons t ev)
            (Trace.ofEvents (Trace.events tr')) := by
              simp [Trace.ofEvents, List.foldl_append]
      _ = Trace.cons tr' ev := by
              simp [ih]


/-- Concrete two-event regression: chronological JSON order matches `Trace.events`. -/
example (e0 e1 : Event) :
    Trace.events (Trace.ofEvents [e0, e1]) = [e0, e1] :=
  trace_events_ofEvents [e0, e1]

/-- Concrete three-event regression: chronological JSON order matches `Trace.events`. -/
example (e0 e1 e2 : Event) :
    Trace.events (Trace.ofEvents [e0, e1, e2]) = [e0, e1, e2] :=
  trace_events_ofEvents [e0, e1, e2]

/--
**Meaning:** Append distributes over `Trace.cons` on the right.

**Trusted use:** Inductive compositional safety/NI proofs under append.
-/
theorem trace_append_cons (tr1 tr' : Trace) (ev : Event) :
    Trace.append tr1 (Trace.cons tr' ev) = Trace.cons (Trace.append tr1 tr') ev := by
  rfl

/--
**Meaning:** Appending an empty trace is identity on the left.

**Trusted use:** Compositional NI and safety append lemmas.
-/
theorem trace_append_empty_left (tr : Trace) :
    Trace.append Trace.empty tr = tr := by
  induction tr with
  | empty => rfl
  | cons tr' ev ih =>
    simp [Trace.append, ih]

/--
**Meaning:** Appending to empty is identity on the right.

**Trusted use:** Compositional NI and safety append lemmas.
-/
theorem trace_append_empty_right (tr : Trace) :
    Trace.append tr Trace.empty = tr := by
  cases tr <;> rfl

/--
**Meaning:** Chronological append concatenates oldest-first event lists.

**Trusted use:** Compositional safety and observational projection under append.
-/
theorem trace_append_spec (tr1 tr2 : Trace) :
    Trace.events (Trace.append tr1 tr2) = Trace.events tr1 ++ Trace.events tr2 := by
  induction tr2 with
  | empty => simp [Trace.append, Trace.events]
  | cons tr' ev ih =>
    simp [Trace.append, Trace.events, trace_events_cons, ih, List.append_assoc]

/--
**Meaning:** The empty trace is trivially safe.

**Trusted use:** Base case for trace-safety induction and empty-trace decider proofs.

**Does not imply:** Any runtime activity occurred or was authorized.
-/
theorem traceSafe_empty : TraceSafe Trace.empty := trivial

/--
**Meaning:** A cons trace is safe exactly when its prefix is safe and the new head event is safe.

**Trusted use:** Structural reasoning and `traceSafe_cons` in generated prop-level proofs.

**Does not imply:** Hash-chain integrity or sequential contract composition beyond PF-Core rules.
-/
theorem traceSafe_cons (tr : Trace) (ev : Event) :
    TraceSafe (Trace.cons tr ev) ↔ TraceSafe tr ∧ EventSafe ev := by
  rfl

/--
**Meaning:** The boolean `traceSafeD` decider reflects the `TraceSafe` predicate.

**Trusted use:** Lifting decider results (including `decide` proofs) to Prop-level `TraceSafe`.

**Does not imply:** Decider completeness for artifacts outside the PF-Core JSON mapping.
-/
theorem traceSafeD_sound (tr : Trace) :
    traceSafeD tr = true ↔ TraceSafe tr := by
  induction tr with
  | empty => simp [traceSafeD, TraceSafe]
  | cons tr ev ih =>
    simp [traceSafeD, TraceSafe, eventSafeD_sound, ih, and_left_comm]

/--
**Meaning:** The boolean `eventInD` decider reflects structural `EventIn` membership.

**Trusted use:** Generated proofs referencing event membership in concrete traces.

**Does not imply:** Semantic equality of events beyond structural `Event` equality.
-/
theorem eventInD_sound (ev : Event) (tr : Trace) :
    eventInD ev tr = true ↔ EventIn ev tr := by
  induction tr with
  | empty => simp [eventInD, EventIn]
  | cons tr' e ih =>
    simp [eventInD, EventIn, ih, beq_iff_eq, decide_eq_true_iff]

end PFCore
