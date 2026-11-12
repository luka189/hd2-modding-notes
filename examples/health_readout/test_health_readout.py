"""Tests for health_readout.lua in the fake game.

    python3 examples/health_readout/test_health_readout.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'tools'))
from fakegame import Game, GameCrash, RuleBroken  # noqa: E402

MOD = HERE / 'health_readout.lua'
PLAYER, HELLDIVER, AVATAR = 'un6y1d', 'vvhx8ga', 'u4d1h9a'


def game():
    """Your player object (1) and your Helldiver (2), on full health."""
    g = Game()
    g.declare_type(PLAYER, [AVATAR, 'index'])
    g.declare_type(HELLDIVER, ['health', 'max_health', 'stamina'])
    g.add_object(1, PLAYER, {AVATAR: 2, 'index': 0})
    g.add_object(2, HELLDIVER, {'health': 125, 'max_health': 125, 'stamina': 1.0})
    return g.load(MOD)


def test_shows_health():
    g = game().run(0.5)
    assert g.texts() == 'HP 125', g.texts()


def test_follows_damage_and_turns_red():
    g = game().run(0.5)
    g.set_field(2, 'health', 20)
    g.run(0.1)
    text = [d for d in g.draws if d['kind'] == 'text'][0]
    assert text['text'] == 'HP 20' and (text['r'], text['g']) == (255, 80), text


def test_hidden_while_the_key_is_held_and_by_the_option():
    g = game().run(0.5)
    g.hold('f6')
    g.run(0.1)
    assert g.texts() == ''
    g.release('f6')
    g.run(0.1)
    assert g.texts() == 'HP 125'
    g.set_option('shown', False)
    g.run(0.1)
    assert g.texts() == ''


def test_survives_the_helldiver_going_between_frames():
    # the reinforce: the avatar field still points at the old body for a moment, and the body is gone. A read of
    # its field would end the game; the mod checks the object first, so this runs
    g = game().run(0.5)
    g.remove_object(2)
    g.run(1.0)
    assert g.texts() == ''
    g.add_object(3, HELLDIVER, {'health': 125, 'max_health': 125, 'stamina': 1.0})
    g.set_field(1, AVATAR, 3)
    g.run(0.1)
    assert g.texts() == 'HP 125'


def test_a_new_world_finds_the_player_again():
    g = game().run(0.5)
    g.new_world(mission=True)
    g.remove_object(1)
    g.remove_object(2)
    g.add_object(7, PLAYER, {AVATAR: 8, 'index': 0})
    g.add_object(8, HELLDIVER, {'health': 90, 'max_health': 125, 'stamina': 1.0})
    g.run(4.0)
    assert g.texts() == 'HP 90'


def test_the_fake_catches_an_unchecked_read():
    # the same mod without its check, to show what the fake does with one: the game would read a gone object
    src = MOD.read_text().replace("not alive(s, body, HELLDIVER)", "false")
    g = Game()
    g.declare_type(PLAYER, [AVATAR, 'index'])
    g.declare_type(HELLDIVER, ['health', 'max_health', 'stamina'])
    g.add_object(1, PLAYER, {AVATAR: 2, 'index': 0})
    g.add_object(2, HELLDIVER, {'health': 125, 'max_health': 125, 'stamina': 1.0})
    g.load(source=src)
    try:
        g.run(0.1)
    except RuleBroken as e:
        assert e.rule == 'unchecked_read', e.rule
    else:
        raise AssertionError('no rule broken')
    g.rules['unchecked_read'] = False
    g.run(0.1)
    g.remove_object(2)
    try:
        g.run(0.1)
    except GameCrash as e:
        assert 'gone_object' in str(e), e
    else:
        raise AssertionError('no crash')


if __name__ == '__main__':
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print('ok    ', name)
            except Exception as e:                      # noqa: BLE001
                failed += 1
                print('FAILED', name, type(e).__name__, e)
    print('%d failed' % failed)
    sys.exit(1 if failed else 0)
