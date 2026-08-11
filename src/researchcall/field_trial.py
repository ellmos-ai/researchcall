"""Field trial: many played respondents, one consenting line.

A supervised rehearsal of the live path needs several respondents — a refusal,
a completed interview, a withdrawal — while every call reaches the same briefed
person. The frame cannot express that: a phone number is unique per study, in
the Python guard and again in the database index, because two records sharing a
number would be two people sharing an identity.

So the substitution happens as late as possible, on the wire only. Sample,
attempt, response and register stay per person; just the number handed to the
transport is replaced. That keeps the trial honest in the one direction that
matters: it produces several distinct records, and none of them claims to be a
different human.

The override is fail-closed. A variable that is set but unusable refuses the
whole run rather than falling back to the drawn numbers — those belong to
strangers, and dialing one of them is the single outcome this module exists to
prevent.

**Withdrawal during a trial is role-play, not a request.** The human on the line
is briefed and plays every part, so ``withdrawal_requested`` purges that record
and the run continues. Ending every further call at the first played withdrawal
would make the outcome that most needs rehearsing untestable. The real person's
ways out are the ordinary ones: Ctrl-C, the quota that bounds the run, or
removing the variable.
"""

from __future__ import annotations

import os

from .safety import E164_RE, mask_phone

ENV_VAR = "RESEARCHCALL_FIELD_TRIAL_PHONE"


def trial_phone() -> str | None:
    """The briefed test number, or ``None`` when no trial is configured.

    Raises ``ValueError`` when the variable carries something that is not a
    dialable E.164 number: continuing would send the run to the drawn numbers,
    which is exactly what somebody setting this variable is trying to avoid.
    """
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        return None
    candidate = raw.replace(" ", "")
    if not E164_RE.fullmatch(candidate):
        raise ValueError(
            f"{ENV_VAR} is set to something that is not an E.164 number "
            f"(expected +49…). Refusing to dial: the drawn numbers belong to "
            f"other people."
        )
    return candidate


def routed(sample: dict[str, object], number: str | None) -> dict[str, object]:
    """The sample as the transport sees it: same person, other line."""
    if number is None:
        return sample
    return {**sample, "phone_e164": number}


def marks(number: str | None) -> dict[str, object]:
    """What the attempt record carries so no reader mistakes this for a study."""
    if number is None:
        return {}
    return {"field_trial_routed": True, "field_trial_number": mask_phone(number)}
