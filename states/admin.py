"""
FSM states for admin multi-step workflows.
"""
from aiogram.fsm.state import State, StatesGroup


class AddMovieStates(StatesGroup):
    waiting_for_code        = State()
    waiting_for_title       = State()
    waiting_for_description = State()
    waiting_for_category    = State()
    waiting_for_message_id  = State()


class DeleteMovieStates(StatesGroup):
    waiting_for_code    = State()
    waiting_for_confirm = State()


class EditMovieStates(StatesGroup):
    waiting_for_code        = State()
    waiting_for_field       = State()
    waiting_for_new_value   = State()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirm = State()
