from games_puzzles_algorithms.players.mcts.mcts_agent import UctNode, MctsAgent
from math import sqrt, log
from copy import deepcopy
INF = float('inf')


class RaveNode(UctNode):

    @staticmethod
    def enable_rave(state):
        rave_moves = {}
        state.play_without_tracking_rave_moves = state.play

        def play_while_tracking_rave_moves(action):
            nonlocal rave_moves, state
            if state.player_to_act() not in rave_moves:
                rave_moves[state.player_to_act()] = {}
            if action not in rave_moves[state.player_to_act()]:
                rave_moves[state.player_to_act()][action] = True
            return state.play_without_tracking_rave_moves(action)
        state.play = play_while_tracking_rave_moves

        state.undo_without_tracking_rave_moves = state.undo

        def undo_while_tracking_rave():
            nonlocal rave_moves, state
            player = state.player_who_acted_last()
            action = state.last_action()
            if action in rave_moves[player]:
                del rave_moves[player][action]
            return state.undo_without_tracking_rave_moves()
        state.undo = undo_while_tracking_rave

        state.rave_moves = lambda: rave_moves

    def __init__(self,
                 exploration,
                 limit,
                 action=None,
                 parent=None,
                 acting_player=None):
        super(RaveNode, self).__init__(
            exploration,
            action=action,
            parent=parent,
            acting_player=acting_player)
        self.rave_num_visits = 0
        self._rave_avg_bonus = 0
        self.rave_limit = limit
        assert(self.rave_limit != 0)

    def reset(self): self.__init__(self.exploration, self.rave_limit)

    def ucb(self):
        """Return the upper confidence bound of this node."""
        if self.num_visits > 0:
            alpha = max(0,
                        ((self.rave_limit - self.num_visits)
                         / self.rave_limit))
            value = self.avg_reward() * (1 - alpha)
            value += self._rave_avg_bonus * alpha
            return (value
                    + self.exploration
                    * sqrt(2 * log(self.parent.num_visits) / self.num_visits))
        else:
            if self.exploration > 0:
                return INF
            else:
                return self.avg_reward()

    def lcb(self):
        """Return the lower confidence bound of this node."""
        if self.num_visits > 0:
            alpha = max(0, (self.rave_limit - self.num_visits) /
                        self.rave_limit)
            value = self.avg_reward() * (1 - alpha)
            value += self._rave_avg_bonus * alpha
            return (value
                    - self.exploration
                    * sqrt(2 * log(self.parent.num_visits) / self.num_visits))
        else:
            if self.exploration > 0:
                return -INF
            else:
                return self.avg_reward()

    def value(self): return self.ucb()

    def create_child(self, state, action):
        return type(self)(self.exploration,
                          self.rave_limit,
                          action=action,
                          parent=self,
                          acting_player=state.player_to_act())

    def backup(self, score=0, rave_moves={}):
        """Update the node statistics on the path from the passed node to
        root to reflect the value of the given `simulation_statistics`.
        """
        self.num_visits += 1
        self._avg_reward += (score - self._avg_reward) / self.num_visits

        if rave_moves and self.acting_player in rave_moves:
            for child in self._children:
                if child.action in rave_moves[self.acting_player]:
                    child.rave_num_visits += 1
                    child_score = score
                    if (not self.is_decision_node()
                            and child.acting_player != self.acting_player):
                        child_score = -score
                    child._rave_avg_bonus += ((child_score
                                               - child._rave_avg_bonus)
                                              / child.rave_num_visits)
        if not self.is_root():
            if (not self.parent.is_decision_node()
                    and self.acting_player != self.parent.acting_player):
                score = -score
            self.parent.backup(score=score, rave_moves=rave_moves)

    def info_string(self):
        return (super(RaveNode, self).info_string()
                + (' rave_ucb_value: {} rave_avg_bonus: {} rave_num_visits: {}'.format(
                    self.ucb(),
                    self._rave_avg_bonus,
                    self.rave_num_visits)))

    def statistics_to_dict(self):
        d = super(RaveNode, self).statistics_to_dict()
        d['rave_ucb_value'] = self.ucb()
        d['rave_avg_bonus'] = self._rave_avg_bonus
        d['rave_num_visits'] = self.rave_num_visits
        return d


class RaveAgent(MctsAgent):
    """A Monte Carle Tree Search Agent with Rapid Action Value Estimation."""

    def __init__(self, random_generator, node=None):
        if node is None:
            node = RaveNode(1, 300)
        super(RaveAgent, self).__init__(random_generator, node)

    def search(self, root_state, *args, **kwargs):
        RaveNode.enable_rave(root_state)
        return super(RaveAgent, self).search(root_state, *args, **kwargs)

    def evaluation(self, state, player_of_interest):
        rave_moves = deepcopy(state.rave_moves()) \
            if hasattr(state, 'rave_moves') else None
        return {'score': state.score(player_of_interest),
                'rave_moves': rave_moves}
