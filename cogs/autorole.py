import discord
from discord.ext import commands
from discord import app_commands

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return

        roles = self.bot.db.fetchall(
            "SELECT role_id FROM auto_roles WHERE guild_id = ?",
            (member.guild.id,)
        )
        for (role_id,) in roles:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except discord.Forbidden:
                    pass

    @app_commands.command(name="autorole_add", description="Add a role to be given automatically to new members")
    @app_commands.describe(role="The role to auto-assign on join")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_add(self, interaction: discord.Interaction, role: discord.Role):
        self.bot.db.execute(
            "INSERT OR IGNORE INTO auto_roles (guild_id, role_id) VALUES (?, ?)",
            (interaction.guild.id, role.id)
        )
        await interaction.response.send_message(f"{role.mention} will now be given to all new members.")

    @app_commands.command(name="autorole_remove", description="Stop a role from being auto-assigned to new members")
    @app_commands.describe(role="The role to remove from auto-assign")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_remove(self, interaction: discord.Interaction, role: discord.Role):
        self.bot.db.execute(
            "DELETE FROM auto_roles WHERE guild_id = ? AND role_id = ?",
            (interaction.guild.id, role.id)
        )
        await interaction.response.send_message(f"{role.mention} removed from auto-roles.")

    @app_commands.command(name="autorole_list", description="List all roles that are auto-assigned to new members")
    async def autorole_list(self, interaction: discord.Interaction):
        rows = self.bot.db.fetchall(
            "SELECT role_id FROM auto_roles WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if not rows:
            return await interaction.response.send_message("No auto-roles configured.", ephemeral=True)

        mentions = []
        for (role_id,) in rows:
            role = interaction.guild.get_role(role_id)
            if role:
                mentions.append(role.mention)

        embed = discord.Embed(
            title="Auto-Roles",
            description="\n".join(mentions) if mentions else "No valid roles found.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
