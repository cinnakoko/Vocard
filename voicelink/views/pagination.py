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
import traceback

from .utils import Pagination, BaseModal

class PaginationView(discord.ui.View):
    def __init__(self, pagination: Pagination, author: discord.Member, timeout = 300):
        super().__init__(timeout=timeout)
        
        self.pagination: Pagination = pagination
        self.author: discord.Member = author
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
    
    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        traceback.print_exception(error)
    
    async def update_message(self, interaction: discord.Interaction) -> None:
        """Update the view and edit the message."""
        
    @discord.ui.button(label='<<', custom_id="fast_back")
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Jump to the first page."""
        self.pagination.go_page(0)
        await self.update_message(interaction)

    @discord.ui.button(label='Back', custom_id="back", style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the previous page if it exists."""
        self.pagination.go_back()
        await self.update_message(interaction)

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
        await self.update_message(interaction)

    @discord.ui.button(label='Next', custom_id="next", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the next page if it exists."""
        self.pagination.go_next()
        await self.update_message(interaction)

    @discord.ui.button(label='>>', custom_id="fast_next")
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Jump to the last page."""
        self.pagination.go_page(self.pagination.total_pages - 1)
        await self.update_message(interaction)