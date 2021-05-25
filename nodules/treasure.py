from . import CoreNodule
from discord import Embed, Colour


class Nodule(CoreNodule):
    def __init__(self, client):
        self.roles = {
            "🟨": 810245249711603782,
            "🟥": 810245249711603782,
            "🟩": 810245345094664243,
            "🟦": 810245370742439946,
            "⬛": 831167907769221140
        }

        self.house_channels = {"⬛": 846827904502595605}

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
                # name = row["name"]
                team_id = row["id"]
                print(team_id)
                color = Colour.from_rgb(*tuple(int(row["color"][i + 1:i + 3], 16)
                                               for i in (0, 2, 4)))

                # List the things that have been collected
                text = "**You've collected:**\n"
                cursor = self.client.dbconn.execute(
                    "SELECT treasure.id, treasure.name, treasure.value FROM collected INNER JOIN "
                    "treasure ON treasure.id=collected.item WHERE collected.team = ?", (team_id,))
                for row in cursor:
                    text += "{:2d}. {} ({})\n".format(row["id"], row["name"], row["value"])

                # List things yet to collect
                text += "\n**You can still collect:**\n"
                cursor = self.client.dbconn.execute(
                    "SELECT treasure.id, treasure.name, treasure.value FROM treasure LEFT JOIN "
                    "(SELECT * FROM collected WHERE collected.team=?) AS coll ON "
                    "coll.item=treasure.id WHERE coll.id IS NULL", (team_id,))
                for row in cursor:
                    text += "{:2d}. {} ({})\n".format(row["id"], row["name"], row["value"])
                embed = Embed(title="The Scavenger Hunt", description=text, color=color)

                # Point totals
                cursor = self.client.dbconn.execute(
                    "SELECT teams.name, sum(treasure.value) as points FROM collected INNER JOIN "
                    "treasure ON collected.item = treasure.id INNER JOIN teams ON collected.team = "
                    "teams.id GROUP BY collected.team")
                for row in cursor:
                    embed.add_field(name=row["name"], value="{:.2f}".format(row["points"]))
                await message.channel.send(embed=embed)
            else:
                text = ""
                cursor = self.client.dbconn.execute("SELECT id, name, value FROM treasure")
                for row in cursor:
                    text += "{:2d}. **{}** ({})\n".format(row["id"], row["name"], row["value"])

                embed = Embed(title="The Scavenger Hunt", description=text,
                              colour=Colour.from_rgb(194, 124, 14))
                cursor = self.client.dbconn.execute("SELECT teams.name, sum(treasure.value) as "
                                                    "points FROM collected INNER JOIN treasure ON "
                                                    "collected.item = treasure.id INNER JOIN teams "
                                                    "ON collected.team = teams.id GROUP BY "
                                                    "collected.team")
                for row in cursor:
                    embed.add_field(name=row["name"], value="{:.2f}".format(row["points"]))
                await message.channel.send(embed=embed)

        if message_text.startswith('!collected') and message.author.guild_permissions.administrator:
            if message.channel.id in self.house_channels.values():
                # Get team details
                cursor = self.client.dbconn.execute("SELECT * FROM teams WHERE teams.channel_id=?",
                                                    (message.channel.id,))
                row = cursor.fetchone()
                # name = row["name"]
                team_id = row["id"]
                color = Colour.from_rgb(*tuple(int(row["color"][i + 1:i + 3], 16)
                                               for i in (0, 2, 4)))

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
                    await message.channel.send("You have already collected this item.")
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
                embed = Embed(description=f"You have collected **{item_name}** ({item_value} "
                                          f"points). Your total is now {total:.2f} points!",
                              color=color)
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
