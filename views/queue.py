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

from typing import TYPE_CHECKING

from .utils import Pagination, BaseModal

if TYPE_CHECKING:
    from voicelink import Player, Track


class QueueView(discord.ui.View):
    """
    A Discord UI view for displaying and interacting with a paginated list of tracks.

    Attributes:
        player (Player): The player containing the track queue or history.
        author (discord.Member): The member who initiated the view.
        is_queue (bool): Indicates if the list is a queue or history.
        pagination (Pagination[Track]): Manages pagination of track lists.
        response (discord.Message): The message containing the view.
        total_duration (str): The total duration of the tracks.
    """

    def __init__(self, player: "Player", author: discord.Member, is_queue: bool = True) -> None:
        super().__init__(timeout=60)
        self.player: Player = player
        self.author: discord.Member = author
        self.is_queue: bool = is_queue
        self.response: discord.Message = None

        self.pagination = Pagination["Track"](
            items=player.queue.tracks() if is_queue else list(reversed(player.queue.history())),
            page_size=7,
        )

        self.total_duration = self.calculate_total_duration()
        self.update_view()

    def calculate_total_duration(self) -> str:
        """Calculate the total duration of the tracks."""
        try:
            return func.time(sum(track.length for track in self.pagination._items))
        except Exception:
            return "∞"

    def format_description(self, tracks: list["Track"], texts: list[str]) -> str:
        """Format the description for the embed based on current tracks."""
        now_playing = (
            texts[1].format(self.player.current.uri,
                            f"```{self.player.current.title}```")
            if self.player.current else texts[2].format("None")
        )

        track_list = "\n".join([
            f"{track.emoji} `{i:>2}.` `[{texts[3] if track.is_stream else func.time(track.length)}]` "
            f"[{func.truncate_string(track.title)}]({track.uri}) {track.requester.mention}"
            for i, track in enumerate(tracks, start=self.pagination.start_index + 1)
        ])

        return f"{now_playing}\n**{texts[4] if self.is_queue else texts[5]}**\n{track_list}"

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

    async def on_timeout(self) -> None:
        """Disable all buttons when the view times out."""
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except discord.HTTPException:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the author of the view can interact with it."""
        return interaction.user == self.author

    async def build_embed(self) -> discord.Embed:
        """Build the embed for the current page of tracks."""
        tracks = self.pagination.get_current_page_items()
        texts = await func.get_lang(
            self.author.guild.id,
            "viewTitle",
            "viewDesc",
            "nowplayingDesc",
            "live",
            "queueTitle",
            "historyTitle",
            "viewFooter",
        )

        embed = discord.Embed(title=texts[0], color=func.settings.embed_color)
        embed.description = self.format_description(tracks, texts)

        embed.set_footer(
            text=texts[6].format(
                self.pagination.current_page,
                self.pagination.total_pages,
                self.total_duration,
            )
        )

        return embed

    async def update_and_edit_message(self, interaction: discord.Interaction) -> None:
        """Update the view and edit the message with the new embed."""
        self.update_view()

        if interaction.response.is_done():
            await interaction.followup.edit_message(self.response.id, embed=await self.build_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=await self.build_embed(), view=self)

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
