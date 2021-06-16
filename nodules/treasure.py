from . import CoreNodule
from discord import Embed, Colour


class Nodule(CoreNodule):
    def __init__(self, client):
        self.roles = {
            "🟦": 854402152252047420,    # hemi-demi-semi-colon
            "🟥": 854402714842824714,    # interrobang
            "🟨": 854402714842824714,    # quasiquote
            "🟩": 854402900046250036,    # sarcastrophe
        }

        self.house_channels = {
            "🟦": 854404551783088129,
            "🟥": 854404623230173244,
            "🟨": 854404586566713387,
            "🟩": 853350268464267284,
        }

        client.dbconn.execute('''CREATE TABLE IF NOT EXISTS "treasure" (
                                 "id" INTEGER UNIQUE,
                                 "name" TEXT,
                                 "value" NUMERIC,
                                 PRIMARY KEY("id" AUTOINCREMENT)
                                 );''')
        client.dbconn.execute('''CREATE TABLE IF NOT EXISTS "teams" (
                                 "id" INTEGER UNIQUE,
                                 "name" TEXT,
                                 "role_id" INTEGER,
                                 "channel_id" INTEGER,
                                 "color" TEXT,
                                 PRIMARY KEY("id" AUTOINCREMENT)
                                 );''')
        client.dbconn.execute('''CREATE TABLE IF NOT EXISTS "collected" (
                                 "id" INTEGER UNIQUE,
                                 "team" INTEGER,
                                 "item" INTEGER,
                                 PRIMARY KEY("id" AUTOINCREMENT),
                                 FOREIGN KEY("team") REFERENCES "teams"("id"),
                                 FOREIGN KEY("item") REFERENCES "treasure"("id")
                                 );''')

        super().__init__(client)

    async def on_message(self, message):
        message_text = message.content

        # Show a list of items that can be collected
        if message_text.startswith('!treasure'):
            if message.channel.id in self.house_channels.values():
                # Get team details
                cursor = self.client.dbconn.execute("SELECT * FROM teams WHERE teams.channel_id=?",
                                                    (message.channel.id,))
                row = cursor.fetchone()
                team_id = row["id"]
                colour = get_colour(row["color"])

                # List the things that have been collected
                items_text = "**You've collected:**\n"
                cursor = self.client.dbconn.execute(
                    "SELECT treasure.id, treasure.name, treasure.value FROM collected INNER JOIN "
                    "treasure ON treasure.id=collected.item WHERE collected.team = ?", (team_id,))
                for row in cursor:
                    items_text += f"{row['id']}. {row['name']} ({row['value']})\n"

                # List things yet to collect
                items_text += "\n**You can still collect:**\n"
                cursor = self.client.dbconn.execute(
                    "SELECT treasure.id, treasure.name, treasure.value FROM treasure LEFT JOIN "
                    "(SELECT * FROM collected WHERE collected.team=?) AS coll ON "
                    "coll.item=treasure.id WHERE coll.id IS NULL", (team_id,))
                for row in cursor:
                    items_text += f"{row['id']}. {row['name']} ({row['value']})\n"
            else:
                items_text = ""
                colour = get_colour("000000")
                cursor = self.client.dbconn.execute("SELECT id, name, value FROM treasure")
                for row in cursor:
                    items_text += f"{row['id']}. {row['name']} ({row['value']})\n"

            items = Embed(title="The items.", description=items_text, color=colour)
            await message.channel.send(embed=items)

            points_text = ""
            cursor = self.client.dbconn.execute(
                "SELECT teams.name, sum(treasure.value) as points FROM collected INNER JOIN "
                "treasure ON collected.item = treasure.id INNER JOIN teams ON collected.team = "
                "teams.id GROUP BY collected.team")
            for row in cursor:
                points_text += f"**{row['name']}**\n{row['points']} points\n"

            points = Embed(title="The points.", description=points_text, color=colour)
            await message.channel.send(embed=points)

        if message_text.startswith('!collected'):
            # Check whether the author is in the right role
            can_mark_collected = False
            for role in message.author.roles:
                if role.id == 854633129938386945:
                    can_mark_collected = True

            if can_mark_collected and message.channel.id in self.house_channels.values():
                # Get team details
                cursor = self.client.dbconn.execute("SELECT * FROM teams WHERE teams.channel_id=?",
                                                    (message.channel.id,))
                row = cursor.fetchone()
                team_id = row["id"]
                team_name = row["name"]
                colour = get_colour(row["color"])

                # Get item details
                try:
                    item_id = int(message_text[11:])
                    cursor = self.client.dbconn.execute("SELECT * FROM treasure WHERE id=?",
                                                        (item_id,))
                    row = cursor.fetchone()
                    item_name = row["name"]
                    item_value = row["value"]
                except (ValueError, TypeError):
                    await message.channel.send("You need to provide item id as a valid integer.")
                    return

                # Check if item already collected
                cursor = self.client.dbconn.execute("SELECT * FROM collected WHERE team=? AND "
                                                    "item=?", (team_id, item_id,))
                if cursor.fetchone():
                    await message.channel.send("This item has already been collected.")
                    return

                # Insert the collection
                self.client.dbconn.execute("INSERT INTO collected (team, item) VALUES (?, ?)",
                                           (team_id, item_id))
                self.client.dbconn.commit()

                # Get the sum
                cursor = self.client.dbconn.execute(
                    "SELECT sum(treasure.value) as points FROM collected INNER JOIN treasure ON "
                    "collected.item = treasure.id WHERE collected.team=?",
                    (team_id,))
                row = cursor.fetchone()
                total = row["points"]

                # Send the embed
                embed = Embed(description=f"{team_name.title()} has collected **{item_name}** "
                                          f"({item_value}). Their total is now {total} points!",
                              color=colour)
                await message.channel.send(embed=embed)

    async def on_raw_reaction_add(self, payload):
        if payload.channel_id == 807945982556897301 and payload.message_id == 810241676937003018:
            role_ids = [x.id for x in payload.member.roles]
            if (not any([x in role_ids for x in self.roles.values()])) and (payload.emoji.name in
                                                                            self.roles.keys()):
                role = self.client.picoguild.get_role(self.roles[payload.emoji.name])
                await payload.member.add_roles(role)

                # Send welcome message
                cursor = self.client.dbconn.execute("SELECT * FROM teams WHERE teams.role_id=?",
                                                    (self.roles[payload.emoji.name],))
                row = cursor.fetchone()
                await self.client.get_channel(row["channel_id"]).send(
                    "Welcome to Team **{}**, <@{}>!".format(row["name"], payload.member.id))

def get_colour(hex_code):
    return Colour.from_rgb(*tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4)))
