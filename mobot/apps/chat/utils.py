import re
from typing import Callable, List, Set, NewType
from mobot.apps.merchant_services.models import DropSession
from mobot.apps.chat.models import MobotChatSession

from mobot.apps.chat.context import MobotContext

MobotContextFilter = NewType('MobotContextFilter', Callable[[MobotContext], bool])


def regex_filter(regex: str) -> MobotContextFilter:
    compiled_regex = re.compile(regex)

    def matches(ctx: MobotContext):
        if re.search(compiled_regex, ctx.message.text):
            return True
        return False

    return matches


def drop_session_state_filter(states: Set[DropSession.State]) -> MobotContextFilter:
    def _filter(ctx: MobotContext):
        return ctx.drop_session.state in states if states else True

    return _filter


def chat_session_state_filter(states: Set[MobotChatSession.State]) -> MobotContextFilter:
    def _filter(ctx: MobotContext):
        return ctx.chat_session.state in states if states else True

    return _filter
