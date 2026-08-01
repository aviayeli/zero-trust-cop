"""One offline training episode, driven straight against GameEpisode.

Rewards are SPARSE: only the transition that TERMINATES the episode carries
the engine's outcome reward, and every earlier transition learns from zero.
Paying a survival reward each turn would reward an agent for merely existing
and swamp the terminal signal it is meant to learn from (PLAN_05 Conductor
ruling; distance shaping was rejected there for the same reason).
"""

NO_REWARD = 0.0


def terminal_outcome(result):
    """Map a TERMINATING TurnResult onto the engine's outcome vocabulary.

    Offline only two outcomes are reachable: the cop captured the thief, or
    the episode ran out of moves. "tie" and "technical_loss" arise from the
    live protocol and cannot occur with two in-process policies.
    """
    return "capture" if result.captured else "survival"


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
            cop_reward = cop.qvalues.reward("cop", outcome)
            thief_reward = thief.qvalues.reward("thief", outcome)
            scores = (cop_reward, thief_reward)
        else:
            cop_reward = thief_reward = NO_REWARD

        cop.learn(state_cop, cop_move, cop_reward, next_cop, terminal)
        thief.learn(state_thief, thief_move, thief_reward, next_thief, terminal)

        cop.observe_opponent(
            "thief", thief_intent, thief_move, result.thief_position
        )
        thief.observe_opponent("cop", cop_intent, cop_move, result.cop_position)

    return scores
