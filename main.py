import asyncio
import datetime

from distee.client import Client
from distee.components import Modal, ActionRow, TextInput, Button
from distee.enums import TextInputType
from distee.flags import Intents
from distee.interaction import Interaction
from distee.application_command import *
from distee.channel import TextChannel
import json

with open('config.json') as f:
    cfg = json.load(f)

intents = Intents.default()
client = Client()
client.message_cache_size = 0

guild_id = cfg.get('guild_id')
on_topic_channel_id = cfg.get('on_topic_channel')
review_channel_id = cfg.get('review_channel')

cooldown_till: datetime.datetime = None
offset = datetime.timedelta(hours=cfg['cooldown']['hours'],
                            minutes=cfg['cooldown']['minutes'],
                            seconds=cfg['cooldown']['seconds'])

C_GREEN = 0x57F287
C_RED = 0xED4245
C_BLURPLE = 0x7289DA


@client.interaction_handler('btn_approve')
async def approve_interaction(inter: Interaction):
    await inter.defer_send()
    msg = inter.message
    embed = msg.embeds[0]
    topic = embed.get('description')
    author = embed.get('fields')[0].get('value')
    guild = client.get_guild(inter.guild_id)
    channel: TextChannel = guild.get_channel(on_topic_channel_id)
    await channel.send(embeds=[{
            'title': 'New Topic',
            'description': f'**{topic}**\n\nTopic suggestions are now on cooldown!',
            'color': C_GREEN
        }],
        allowed_mentions={
            'users': [int(author[2:-1])]
        },
        content=f'Thanks {author} for suggesting the new topic!'
    )
    # reset cooldown
    global cooldown_till
    cooldown_till = datetime.datetime.utcnow() + offset
    safe_state()
    # set channel topic
    await channel.change_topic(f'Current discussion topic: {topic}')
    # lets remove the buttons
    embed['color'] = C_GREEN
    await msg.edit(embeds=[embed], components=[])

    # set interaction response
    await inter.send_followup(embeds=[{
        'title': 'Topic approved',
        'description': f'{topic}\n\nApproved by <@{inter.member.id}>',
        'color': C_GREEN
    }])


@client.interaction_handler('btn_deny')
async def deny_interaction(inter: Interaction):
    await inter.defer_send()
    msg = inter.message
    embed = msg.embeds[0]
    topic = embed.get('description')
    author = embed.get('fields')[0].get('value')
    guild = client.get_guild(inter.guild_id)
    channel: TextChannel = guild.get_channel(on_topic_channel_id)
    await channel.send(f'Hey {author}! Your topic "{topic}" has been rejected.',
                       allowed_mentions={'users': [author[2:-1]]})
    embed['color'] = C_RED
    await msg.edit(embeds=[embed], components=[])

    await inter.send_followup(embeds=[{
        'title': 'Topic denied',
        'color': C_RED,
        'description': f'{topic}\n\nDenied by <@{inter.member.id}>'
    }])


@client.interaction_handler('topic_suggestion')
async def topic_suggestion_callback(inter: Interaction):
    topic = inter.data.components['topic']['value'].strip()
    if len(topic) == 0:
        await inter.send(embeds=[{'description': 'You have to actually suggest a topic!',
                                  'color': C_RED}], ephemeral=True,
                         components=[
                             ActionRow([
                                 Button('btn_retry',
                                        label='Try again')
                             ])
                         ])
        return
    await inter.defer_send(ephemeral=True)
    guild = client.get_guild(inter.guild_id)
    review_channel: TextChannel = guild.get_channel(review_channel_id)
    await review_channel.send(
        embeds=[{
            'title': 'New discussion Topic',
            'description': topic,
            'color': C_BLURPLE,
            'fields': [
                {'name': 'Author', 'value': f'<@{inter.member.id}>'}]
        }],
        components=[{
            'type': 1,
            'components': [{
                'type': 2,
                'label': 'Approve',
                'style': 3,
                'custom_id': 'btn_approve'
            }, {
                'type': 2,
                'label': 'Deny',
                'style': 4,
                'custom_id': 'btn_deny'
            }]
        }])
    await inter.send_followup(embeds=[{
        'title': 'Your topic was send to review.',
        'color': C_GREEN
    }], ephemeral=True)
    pass


@client.interaction_handler('btn_retry')
async def suggest_topic_command(inter: Interaction):
    if inter.channel_id.id != on_topic_channel_id:
        await inter.send(embeds=[{
            'description': f'You can only use this command in the <#{on_topic_channel_id}> channel.',
            'color': C_RED
        }], ephemeral=True)
        return
    if cooldown_till is not None:
        await inter.send(embeds=[{
            'description': 'Topic suggestion is still on cooldown.',
            'color': C_RED
        }], ephemeral=True)
        return
    modal = Modal('topic_suggestion',
                  'Topic suggestion',
                  components=[
                    ActionRow([
                        TextInput('topic',
                                  'Your topic suggestion',
                                  style=TextInputType.PARAGRAPH,
                                  placeholder='The topic you want to suggest')
                    ])
                  ])
    await inter.send_modal(modal)


# register slash command
ap = ApplicationCommand(name='topic',
                        description='Suggest a new topic',
                        type=ApplicationCommandType.CHAT_INPUT)
# register as local command on all servers
client.register_command(ap, suggest_topic_command, True, None)


def load_state():
    global cooldown_till
    data = {}
    try:
        with open('state.json', 'r') as fi:
            data = json.load(fi)
    except:
        pass
    datestr = data.get('cooldown')
    cooldown_till = None if datestr is None else datetime.datetime.fromisoformat(datestr)


def safe_state():
    with open('state.json', 'w') as fi:
        json.dump({'cooldown': cooldown_till.isoformat() if cooldown_till is not None else None}, fi)


async def check_cooldown():
    global cooldown_till
    while True:
        await asyncio.sleep(10)
        if cooldown_till is not None:
            if datetime.datetime.utcnow() >= cooldown_till:
                cooldown_till = None
                safe_state()
                guild = client.get_guild(guild_id)
                await guild.get_channel(review_channel_id).send(embeds=[{
                    'title': 'Cooldown elapsed',
                    'color': C_BLURPLE
                }])
                await guild.get_channel(on_topic_channel_id).send(embeds=[{
                    'title': 'Topic submissions are now open',
                    'description': 'use /topic to submit a new topic',
                    'color': C_BLURPLE
                }])
                

load_state()
asyncio.ensure_future(check_cooldown())
client.run(cfg.get('token'), intents)
