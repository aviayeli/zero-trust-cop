"""One offline training episode, driven straight against GameEpisode.

The OUTCOME reward is still sparse — only the terminating transition pays the
engine's payoff, and a per-turn survival reward is still refused for the reason
PLAN_05 gave: it would pay an agent for merely existing. Two much smaller
SHAPING terms sit on top of it, because terminal-only rewards left the learner
unable to distinguish a wasted turn from a useful one:

* ``invalid_move_penalty`` when a non-STAY move leaves the agent where it was.
  Without it, grinding into the north wall costs exactly what advancing costs,
  which is how a degenerate "always N" policy survives training.
* ``step_cost``, a living penalty on every non-capture turn, so the shortest
  path to a capture is the most valuable one.

Both are read from each peer's private ``[strategy]`` block and both are two
orders of magnitude below the terminal payoffs, so the outcome still dominates:
a full 35-move match of ``step_cost`` is ``-0.35`` against a capture worth 20.
Distance shaping remains rejected — neither term looks at the opponent.
"""

from engine.actions import Action

NO_REWARD = 0.0


def terminal_outcome(result):
    """Map a TERMINATING TurnResult onto the engine's outcome vocabulary.

    Offline only two outcomes are reachable: the cop captured the thief, or
    the episode ran out of moves. "tie" and "technical_loss" arise from the
    live protocol and cannot occur with two in-process policies.
    """
    return "capture" if result.captured else "survival"


def shaping_reward(settings, move, before, after, captured):
    """Return the per-turn shaping term for one agent.

    A non-STAY move whose resolved cell equals the cell it started from was
    REFUSED — by a barrier or by the board edge, which the engine treats
    alike — and pays ``invalid_move_penalty``. Every turn that does not end in
    a capture also pays ``step_cost``. STAY is a legal choice and is never
    treated as a refused move.
    """
    reward = NO_REWARD
    if move != Action.STAY.value and after == before:
        reward += settings.invalid_move_penalty
    if not captured:
        reward += settings.step_cost
    return reward


def _last_resolved(episode, position):
    """Return the opponent's last RESOLVED cell, or None before any turn.

    Returning None on turn 0 is what exercises the D2 fallback: the policy
    then asks its pheromone field instead, which is empty and yields None.
    """
    return position if episode.turn_count > 0 else None


def play_episode(episode, cop, thief, rng_cop, rng_thief):
    """Play one episode to termination; return its (cop_score, thief_score)."""
    episode.reset()
    scores = (NO_REWARD, NO_REWARD)

    while not episode.is_terminated:
        state_cop = cop.state_key(
            episode.cop_state.position,
            _last_resolved(episode, episode.thief_state.position),
            episode.board,
        )
        state_thief = thief.state_key(
            episode.thief_state.position,
            _last_resolved(episode, episode.cop_state.position),
            episode.board,
        )

        cop_move, cop_intent = cop.decide(state_cop, rng_cop)
        thief_move, thief_intent = thief.decide(state_thief, rng_thief)

        cop_before = episode.cop_state.position
        thief_before = episode.thief_state.position
        result = episode.step(cop_move, thief_move)
        terminal = episode.is_terminated

        next_cop = cop.state_key(
            result.cop_position, result.thief_position, episode.board
        )
        next_thief = thief.state_key(
            result.thief_position, result.cop_position, episode.board
        )

        if terminal:
            outcome = terminal_outcome(result)
            cop_outcome = cop.qvalues.reward("cop", outcome)
            thief_outcome = thief.qvalues.reward("thief", outcome)
            # The SCORE is the engine's payoff alone: shaping steers learning
            # and must never leak into what the series reports.
            scores = (cop_outcome, thief_outcome)
        else:
            cop_outcome = thief_outcome = NO_REWARD

        cop_reward = cop_outcome + shaping_reward(
            cop.settings, cop_move, cop_before, result.cop_position, result.captured
        )
        thief_reward = thief_outcome + shaping_reward(
            thief.settings, thief_move, thief_before, result.thief_position,
            result.captured,
        )

        cop.learn(state_cop, cop_move, cop_reward, next_cop, terminal)
        thief.learn(state_thief, thief_move, thief_reward, next_thief, terminal)

        cop.observe_opponent(
            "thief", thief_intent, thief_move, result.thief_position
        )
        thief.observe_opponent("cop", cop_intent, cop_move, result.cop_position)

    return scores
