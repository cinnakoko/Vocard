"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import discord
import function as func

from math import ceil
from tldextract import extract
from discord.ext import commands
from typing import Any, TYPE_CHECKING, reveal_type

from .utils import DynamicViewManager, Pagination, BaseModal

if TYPE_CHECKING:
    from voicelink import Track


class Select_playlist(discord.ui.Select):
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.view: PlaylistViewManager

        super().__init__(
            placeholder="Select a playlist to view ..",
            custom_id="selector",
            options=[
                discord.SelectOption(
                    emoji=playlist['emoji'],
                    label=f'{index}. {playlist["name"]}',
                    value=playlist["id"],
                    description=f"{playlist['time']} · {playlist['type']}"
                ) for index, playlist in enumerate(results, start=1) if playlist['type'] != 'error'
            ]
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PlaylistView = self.view.change_view(self.values[0])
        await interaction.response.edit_message(embed=await view.build_embed(), view=view)


class PlaylistView(discord.ui.View):
    def __init__(
        self,
        primary_view: "PlaylistViewManager",
        playlist_data: dict[str, Any]
    ) -> None:
        super().__init__(timeout=180)

        self.primary_view: PlaylistViewManager = primary_view
        self.author: discord.Member = primary_view.ctx.author

        self.id: str = playlist_data.get("id")
        self.emoji: str = playlist_data.get("emoji")
        self.name: str = playlist_data.get("name")
        self.time: str = playlist_data.get("time")
        self.type: str = playlist_data.get("type")
        self.owner_id: int = playlist_data.get("owner")
        self.perms: dict[str, list[int]] = playlist_data.get("perms")
        self.pagination: Pagination = Pagination[dict[str, Any]](playlist_data.get("tracks"), page_size=7)

        self.update_view()

    def update_view(self) -> None:
        """Update button states and page number display based on current pagination state."""
        button_states = {
            "fast_back": self.pagination.current_page <= 2,
            "back": not self.pagination.has_previous_page,
            "fast_next": self.pagination.current_page >= self.pagination.total_pages - 1,
            "next": not self.pagination.has_next_page,
        }

        for child in self.children:
            if child.custom_id in button_states:
                child.disabled = button_states[child.custom_id]
            if child.custom_id == "page_number":
                child.label = f"{self.pagination.current_page:02}/{self.pagination.total_pages:02}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def on_error(self, error, item, interaction) -> None:
        return
    
    async def build_embed(self) -> discord.Embed:
        """Build the embed for the current page of tracks."""
        tracks = self.pagination.get_current_page_items()
        texts = await func.get_lang(
            self.author.guild.id,
            "playlistView", "playlistViewDesc", "settingsPermTitle",
            "playlistViewPermsValue", "playlistViewPermsValue2",
            "playlistViewTrack", "playlistNoTrack", "playlistViewFooter"
        )

        embed = discord.Embed(title=texts[0], color=func.settings.embed_color)
        embed.description = texts[1].format(
            self.name,
            self.id,
            self.pagination.total_items,
            self.primary_view.ctx.bot.get_user(self.owner_id),
            self.type.upper()
        ) + "\n"

        embed.description += texts[2] + "\n"
        if self.type == 'share':
            write_perm = '✓' if 'write' in self.perms and self.author.id in self.perms['write'] else '✘'
            remove_perm = '✓' if 'remove' in self.perms and self.author.id in self.perms['remove'] else '✘'
            embed.description += texts[3].format(write_perm, remove_perm)
        else:
            readable_users = ', '.join(f'<@{user}>' for user in self.perms['read'])
            embed.description += texts[4].format(readable_users)

        # Add track information
        embed.description += f"\n\n**{texts[5]}:**\n"
        if tracks:
            for index, track in enumerate(tracks, start=self.pagination.start_index + 1):
                if self.type == "playlist":
                    source_emoji = func.get_source(track['sourceName'], 'emoji')
                    track_info = f"{source_emoji} `{index:>2}.` `[{func.time(track['length'])}]` [{func.truncate_string(track['title'])}]({track['uri']})"
                else:
                    source_emoji = func.get_source(extract(track.info['uri']).domain, 'emoji')
                    track_info = f"{source_emoji} `{index:>2}.` `[{func.time(track.length)}]` [{func.truncate_string(track.title)}]({track.uri})"
                embed.description += track_info + "\n"
        else:
            embed.description += texts[6].format(self.name)

        # Set the footer
        embed.set_footer(text=texts[7].format(self.time))
        return embed

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.primary_view.response.edit(view=self)
        except:
            pass

    async def update_and_edit_message(self, interaction: discord.Interaction) -> None:
        """Update the view and edit the message with the new embed."""
        self.update_view()

        if interaction.response.is_done():
            await interaction.followup.edit_message(self.primary_view.response.id, embed=await self.build_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        """Handle errors that occur during interaction."""
        func.logger.error(f"Error in PlaylistView: {error}", exc_info=error)

    @discord.ui.button(label='<<', custom_id="fast_back")
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Jump to the first page."""
        self.pagination.go_page(0)
        await self.update_and_edit_message(interaction)

    @discord.ui.button(label='Back', custom_id="back", style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the previous page if it exists."""
        self.pagination.go_back()
        await self.update_and_edit_message(interaction)

    @discord.ui.button(label="--/--", custom_id="page_number", style=discord.ButtonStyle.blurple)
    async def page_number(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Display current page number."""
        modal = BaseModal(
            title="Page Number",
            custom_id="page_number_modal",
            items=[
                discord.ui.TextInput(
                    label="Page Number",
                    custom_id="page_number",
                    placeholder="Enter the page number to navigate.",
                    default=str(self.pagination.current_page),
                    max_length=5,
                    required=True
                )
            ]
        )
        await interaction.response.send_modal(modal)
        await modal.wait()

        page_number = modal.values.get("page_number")
        if not page_number or not page_number.isdigit():
            return

        self.pagination.go_page(int(page_number) - 1)
        await self.update_and_edit_message(interaction)

    @discord.ui.button(label='Next', custom_id="next", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the next page if it exists."""
        self.pagination.go_next()
        await self.update_and_edit_message(interaction)

    @discord.ui.button(label='>>', custom_id="fast_next")
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Jump to the last page."""
        self.pagination.go_page(self.pagination.total_pages - 1)
        await self.update_and_edit_message(interaction)

    @discord.ui.button(label="<")
    async def back_to_home(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Return to the main playlist view."""
        view: PlaylistViewManager = self.primary_view.change_view("home")
        await interaction.response.edit_message(embed=await view.build_embed(), view=view)
    
    @discord.ui.button(label="Play", style=discord.ButtonStyle.green)
    async def play_all(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()
        cmd = interaction.client.get_command("playlist play")
        await cmd(self.primary_view.ctx, self.name)
        # Need to handle error
    
    @discord.ui.button(label="Share", style=discord.ButtonStyle.blurple)
    async def share(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="Export", style=discord.ButtonStyle.gray)
    async def export(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()
        cmd = interaction.client.get_command("playlist export")
        await cmd(self.primary_view.ctx, self.name)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()
        cmd = interaction.client.get_command("playlist delete")
        await cmd(self.primary_view.ctx, name=self.name)
    

class PlaylistViewManager(DynamicViewManager):
    def __init__(self, ctx: commands.Context, results: list[dict[str, Any]]):
        self.ctx: commands.Context = ctx
        self.results: list[dict[str, Any]] = results
        
        views = {"home": self}
        views.update({result["id"]: PlaylistView(self, result) for result in results})
        
        super().__init__(views=views, timeout=None)

        self.response: discord.Message = None
        self.add_item(Select_playlist(results))

    def get_width(self, s):
        import unicodedata
        width = 0
        for char in str(s):
            if unicodedata.east_asian_width(char) in ('F', 'W'):
                width += 2
            else:
                width += 1
        return width
    
    def pad_string(self, s, width):
        s = str(s)
        current_width = self.get_width(s)
        padding = width - current_width
        return s + " " * padding
        
    async def build_embed(self) -> discord.Embed:
        """
        Build the embed for the playlist overview.
        
        Returns:
            discord.Embed: The constructed embed with playlist details.
        """
        _, max_p, _ = func.check_roles()
        text = await func.get_lang(self.ctx.guild.id, "playlistViewTitle", "playlistViewHeaders", "playlistFooter")
        
        headers = text[1].split(",")
        headers.insert(0, "")
        content = [headers]

        description = ""
        for index in range(max_p):
            info = self.results[index] if index < len(self.results) else {}
            if info:
                content.append([
                    info.get('emoji', '  '),
                    info.get('id', "-" * 3),
                    f"[{info.get('time', '--:--')}]",
                    info.get('name', "-" * 6),
                    len(info.get('tracks', []))
                ])

        column_widths = [max(self.get_width(str(item)) for item in column) for column in zip(*content)]

        for row in content:
            formatted_row = "   ".join(self.pad_string(item, width) for item, width in zip(row, column_widths))
            description += formatted_row + "\n"
            
        embed = discord.Embed(
            description=f'```{description}```',
            color=func.settings.embed_color
        )

        embed.set_author(
            name=text[0].format(self.ctx.author.display_name),
            icon_url=self.ctx.author.display_avatar.url
        )
        embed.set_footer(text=text[2])
        return embed