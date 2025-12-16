import os
import asyncio
import discord
import pandas as pd
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from openpyxl import Workbook, load_workbook
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from dotenv import load_dotenv

load_dotenv()

class TalentHubBot:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        self.initialized = True
        self.bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
        self.submission_channel_id = 1374018261578027129
        self.pending_submissions: Dict[str, dict] = {}
        self.pending_updates: Dict[str, dict] = {}
        self.excel_file = "Atalent_submissions.xlsx"
        self.bot_code = os.getenv("DISCORD_BOT")
        
        self._ensure_excel_file()
        
        self.bot.event(self.on_ready)
        self.bot.event(self.on_interaction)
        
        # Register slash commands
        self.bot.tree.command(name="show")(self.show_command)
        self.bot.tree.command(name="show_simple")(self.show_simple_command)
        self.bot.tree.command(name="change")(self.change_command)
        self.bot.tree.command(name="remove")(self.remove_command)
        self.bot.tree.command(name="column_names")(self.column_names_command)
        
        # Register prefix commands
        @self.bot.command(name="show")
        async def show_prefix(ctx):
            await self.show_prefix_command(ctx)
            
        @self.bot.command(name="show_simple")
        async def show_simple_prefix(ctx):
            await self.show_simple_prefix_command(ctx)
            
        @self.bot.command(name="change")
        async def change_prefix(ctx, wallet_address: str, column_name: str, *, new_value: str):
            await self.change_prefix_command(ctx, wallet_address, column_name, new_value)
            
        @self.bot.command(name="remove")
        async def remove_prefix(ctx, wallet_address: str):
            await self.remove_prefix_command(ctx, wallet_address)
            
        @self.bot.command(name="column_names")
        async def column_names_prefix(ctx):
            await self.column_names_prefix_command(ctx)
    
    def _ensure_excel_file(self):
        if not os.path.exists(self.excel_file):
            self._init_excel_file()
        else:
            try:
                wb = load_workbook(self.excel_file)
                ws = wb.active
                expected_headers = [
                    "Name", "Role", "Injective Role", "Experience", "Education", 
                    "Location", "Availability", "Monthly Rate", "Skills", "Languages",
                    "Discord", "Email", "Phone", "Telegram", "X", "Github",
                    "Wallet Address", "Wallet Type", "NFT Holdings", "Token Holdings",
                    "Portfolio", "CV", "Image url", "Bio", "Submission date", "Status"
                ]
                if [cell.value for cell in ws[1]] != expected_headers:
                    # Just recreate without backup
                    os.remove(self.excel_file)
                    self._init_excel_file()
            except Exception as e:
                print(f"Error verifying Excel file: {e}")
                # Just recreate without backup
                if os.path.exists(self.excel_file):
                    os.remove(self.excel_file)
                self._init_excel_file()
    
    def _init_excel_file(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Submissions"
        
        headers = [
            "Name", "Role", "Injective Role", "Experience", "Education", "Location",
            "Availability", "Monthly Rate", "Skills", "Languages", "Discord", "Email",
            "Phone", "Telegram", "X", "Github", "Wallet Address", "Wallet Type",
            "NFT Holdings", "Token Holdings", "Portfolio", "CV", "Image url", "Bio",
            "Submission date", "Status"
        ]
        
        ws.append(headers)
        wb.save(self.excel_file)
    
    async def _find_submission_row(self, wallet_address: str) -> Optional[int]:
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            for row in range(2, ws.max_row + 1):
                if str(ws[f'Q{row}'].value).lower() == wallet_address.lower():
                    wb.close()
                    return row
            
            wb.close()
            return None
            
        except Exception as e:
            print(f"Error searching Excel file: {e}")
            return None
    
    async def _get_all_records(self) -> List[Tuple[str, str]]:
        """Get all wallet addresses and names"""
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            records = []
            for row in range(2, ws.max_row + 1):
                name = ws[f'A{row}'].value
                wallet = ws[f'Q{row}'].value
                if name and wallet:
                    records.append((name, wallet))
            wb.close()
            return records
        except Exception as e:
            print(f"Error getting all records: {e}")
            return []
    
    async def _get_all_records_with_details(self) -> List[dict]:
        """Get all records with detailed information"""
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            records = []
            for row in range(2, ws.max_row + 1):
                # Get key fields
                name = ws[f'A{row}'].value
                wallet = ws[f'Q{row}'].value
                
                if name and wallet:
                    record = {
                        'Name': name,
                        'Role': ws[f'B{row}'].value or 'N/A',
                        'Injective Role': ws[f'C{row}'].value or 'N/A',
                        'Experience': ws[f'D{row}'].value or 'N/A',
                        'Education': ws[f'E{row}'].value or 'N/A',
                        'Location': ws[f'F{row}'].value or 'N/A',
                        'Availability': ws[f'G{row}'].value or 'N/A',
                        'Monthly Rate': ws[f'H{row}'].value or 'N/A',
                        'Skills': ws[f'I{row}'].value or 'N/A',
                        'Languages': ws[f'J{row}'].value or 'N/A',
                        'Discord': ws[f'K{row}'].value or 'N/A',
                        'Email': ws[f'L{row}'].value or 'N/A',
                        'Phone': ws[f'M{row}'].value or 'N/A',
                        'Telegram': ws[f'N{row}'].value or 'N/A',
                        'X': ws[f'O{row}'].value or 'N/A',
                        'Github': ws[f'P{row}'].value or 'N/A',
                        'Wallet Address': wallet,
                        'Wallet Type': ws[f'R{row}'].value or 'N/A',
                        'NFT Holdings': ws[f'S{row}'].value or 'N/A',
                        'Token Holdings': ws[f'T{row}'].value or 'N/A',
                        'Portfolio': ws[f'U{row}'].value or 'N/A',
                        'CV': ws[f'V{row}'].value or 'N/A',
                        'Image url': ws[f'W{row}'].value or 'N/A',
                        'Bio': ws[f'X{row}'].value or 'N/A',
                        'Status': ws[f'Z{row}'].value or 'Pending'
                    }
                    records.append(record)
            wb.close()
            return records
        except Exception as e:
            print(f"Error getting all records with details: {e}")
            return []
    
    async def _delete_record(self, wallet_address: str) -> bool:
        """Delete a record by wallet address"""
        try:
            wb = load_workbook(self.excel_file)
            ws = wb.active
            
            row = await self._find_submission_row(wallet_address)
            if not row:
                wb.close()
                return False
            
            # Delete the row
            ws.delete_rows(row)
            wb.save(self.excel_file)
            wb.close()
            return True
            
        except Exception as e:
            print(f"Error deleting record: {e}")
            return False
    
    async def _update_single_field(self, wallet_address: str, column_name: str, new_value: str) -> bool:
        """Update a single field in a record"""
        try:
            # Column mapping
            column_map = {
                'Name': 'A',
                'Role': 'B',
                'Injective Role': 'C',
                'Experience': 'D',
                'Education': 'E',
                'Location': 'F',
                'Availability': 'G',
                'Monthly Rate': 'H',
                'Skills': 'I',
                'Languages': 'J',
                'Discord': 'K',
                'Email': 'L',
                'Phone': 'M',
                'Telegram': 'N',
                'X': 'O',
                'Github': 'P',
                'Wallet Type': 'R',
                'NFT Holdings': 'S',
                'Token Holdings': 'T',
                'Portfolio': 'U',
                'CV': 'V',
                'Image url': 'W',
                'Bio': 'X',
                'Status': 'Z'
            }
            
            if column_name not in column_map:
                return False
            
            wb = load_workbook(self.excel_file)
            ws = wb.active
            
            row = await self._find_submission_row(wallet_address)
            if not row:
                wb.close()
                return False
            
            # Update the cell
            col = column_map[column_name]
            ws[f'{col}{row}'] = new_value
            
            # Update submission date
            ws[f'Y{row}'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            wb.save(self.excel_file)
            wb.close()
            return True
            
        except Exception as e:
            print(f"Error updating field: {e}")
            return False
    
    async def _get_record_details(self, wallet_address: str) -> Optional[dict]:
        """Get complete record details for a wallet"""
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            row = await self._find_submission_row(wallet_address)
            if not row:
                wb.close()
                return None
            
            record = {}
            columns = [
                ('Name', 'A'), ('Role', 'B'), ('Injective Role', 'C'),
                ('Experience', 'D'), ('Education', 'E'), ('Location', 'F'),
                ('Availability', 'G'), ('Monthly Rate', 'H'), ('Skills', 'I'),
                ('Languages', 'J'), ('Discord', 'K'), ('Email', 'L'),
                ('Phone', 'M'), ('Telegram', 'N'), ('X', 'O'),
                ('Github', 'P'), ('Wallet Address', 'Q'), ('Wallet Type', 'R'),
                ('NFT Holdings', 'S'), ('Token Holdings', 'T'), ('Portfolio', 'U'),
                ('CV', 'V'), ('Image url', 'W'), ('Bio', 'X'), ('Status', 'Z')
            ]
            
            for col_name, col_letter in columns:
                value = ws[f'{col_letter}{row}'].value
                record[col_name] = value if value is not None else "N/A"
            
            wb.close()
            return record
            
        except Exception as e:
            print(f"Error getting record details: {e}")
            return None
    
    async def column_names_command(self, interaction: discord.Interaction):
        """Show all available column names (slash command)"""
        # Use defer to avoid timeout
        await interaction.response.defer()
        
        try:
            valid_columns = [
                'Name', 'Role', 'Injective Role', 'Experience', 'Education',
                'Location', 'Availability', 'Monthly Rate', 'Skills', 'Languages',
                'Discord', 'Email', 'Phone', 'Telegram', 'X', 'Github',
                'Wallet Type', 'NFT Holdings', 'Token Holdings', 'Portfolio',
                'CV', 'Image url', 'Bio', 'Status'
            ]
            
            # Create embed
            embed = discord.Embed(
                title="Available Column Names",
                description="These are the columns you can modify using the /change command:",
                color=discord.Color.blue()
            )
            
            # Add columns in organized groups
            embed.add_field(
                name="Basic Information",
                value="• Name\n• Role\n• Injective Role\n• Experience\n• Education\n• Location\n• Availability\n• Monthly Rate",
                inline=True
            )
            
            embed.add_field(
                name="Skills & Languages",
                value="• Skills\n• Languages",
                inline=True
            )
            
            embed.add_field(
                name="Contact Information",
                value="• Discord\n• Email\n• Phone\n• Telegram\n• X\n• Github",
                inline=True
            )
            
            embed.add_field(
                name="Blockchain Details",
                value="• Wallet Type\n• NFT Holdings\n• Token Holdings",
                inline=True
            )
            
            embed.add_field(
                name="Portfolio & Media",
                value="• Portfolio\n• CV\n• Image url\n• Bio",
                inline=True
            )
            
            embed.add_field(
                name="Status",
                value="• Status",
                inline=True
            )
            
            embed.set_footer(text="Use /change <wallet> <column> <value> to modify these fields")
            
            # Send the embed publicly
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Error in column_names command: {e}")
            await interaction.followup.send(
                "An error occurred while fetching column names.",
                ephemeral=True
            )
    
    async def column_names_prefix_command(self, ctx: commands.Context):
        """Show all available column names (prefix command)"""
        try:
            valid_columns = [
                'Name', 'Role', 'Injective Role', 'Experience', 'Education',
                'Location', 'Availability', 'Monthly Rate', 'Skills', 'Languages',
                'Discord', 'Email', 'Phone', 'Telegram', 'X', 'Github',
                'Wallet Type', 'NFT Holdings', 'Token Holdings', 'Portfolio',
                'CV', 'Image url', 'Bio', 'Status'
            ]
            
            # Create embed
            embed = discord.Embed(
                title="Available Column Names",
                description="These are the columns you can modify using the !change command:",
                color=discord.Color.blue()
            )
            
            # Add columns in organized groups
            embed.add_field(
                name="Basic Information",
                value="• Name\n• Role\n• Injective Role\n• Experience\n• Education\n• Location\n• Availability\n• Monthly Rate",
                inline=True
            )
            
            embed.add_field(
                name="Skills & Languages",
                value="• Skills\n• Languages",
                inline=True
            )
            
            embed.add_field(
                name="Contact Information",
                value="• Discord\n• Email\n• Phone\n• Telegram\n• X\n• Github",
                inline=True
            )
            
            embed.add_field(
                name="Blockchain Details",
                value="• Wallet Type\n• NFT Holdings\n• Token Holdings",
                inline=True
            )
            
            embed.add_field(
                name="Portfolio & Media",
                value="• Portfolio\n• CV\n• Image url\n• Bio",
                inline=True
            )
            
            embed.add_field(
                name="Status",
                value="• Status",
                inline=True
            )
            
            embed.set_footer(text="Use !change <wallet> <column> <value> to modify these fields")
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error in column_names prefix command: {e}")
            await ctx.send("An error occurred while fetching column names.")
    
    async def show_command(self, interaction: discord.Interaction):
        """Show all records in the database with pagination (slash command)"""
        await interaction.response.defer()
        
        try:
            records = await self._get_all_records()
            
            if not records:
                await interaction.followup.send("No records found in the database.")
                return
            
            # Create paginated view
            class PaginatedView(View):
                def __init__(self, records: List[Tuple[str, str]], page: int = 0):
                    super().__init__(timeout=180)
                    self.records = records
                    self.page = page
                    self.records_per_page = 5
                    self.total_pages = (len(records) + self.records_per_page - 1) // self.records_per_page
                
                async def update_message(self, interaction: discord.Interaction):
                    # Calculate start and end indices
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    # Create embed
                    embed = discord.Embed(
                        title="Talent Database",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.blue()
                    )
                    
                    # Add records for current page
                    for i in range(start_idx, end_idx):
                        name, wallet = self.records[i]
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    
                    # Update button states
                    for child in self.children:
                        if child.custom_id == "prev":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next":
                            child.disabled = self.page == self.total_pages - 1
                    
                    await interaction.response.edit_message(embed=embed, view=self)
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, custom_id="prev", disabled=True)
                async def previous_button(self, interaction: discord.Interaction, button: Button):
                    if self.page > 0:
                        self.page -= 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="next")
                async def next_button(self, interaction: discord.Interaction, button: Button):
                    if self.page < self.total_pages - 1:
                        self.page += 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
                async def close_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.edit_message(content="View closed.", embed=None, view=None)
                    self.stop()
            
            # Create initial view
            view = PaginatedView(records)
            await view.update_message(interaction)
            
        except Exception as e:
            print(f"Error in show command: {e}")
            await interaction.followup.send(
                "An error occurred while fetching records.",
                ephemeral=True
            )
    
    async def show_simple_command(self, interaction: discord.Interaction):
        """Show simple list of names and wallets (slash command)"""
        await interaction.response.defer()
        
        try:
            records = await self._get_all_records()
            
            if not records:
                await interaction.followup.send("No records found in the database.")
                return
            
            # Create paginated view for simple view
            class SimplePaginatedView(View):
                def __init__(self, records: List[Tuple[str, str]], page: int = 0):
                    super().__init__(timeout=180)
                    self.records = records
                    self.page = page
                    self.records_per_page = 15  # More records per page for simple view
                    self.total_pages = (len(records) + self.records_per_page - 1) // self.records_per_page
                
                async def update_message(self, interaction: discord.Interaction):
                    # Calculate start and end indices
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    # Create embed
                    embed = discord.Embed(
                        title="Talent Database - Simple View",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.green()
                    )
                    
                    # Add records for current page (in columns)
                    page_records = self.records[start_idx:end_idx]
                    for name, wallet in page_records:
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=True
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    
                    # Update button states
                    for child in self.children:
                        if child.custom_id == "prev_simple":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next_simple":
                            child.disabled = self.page == self.total_pages - 1
                    
                    await interaction.response.edit_message(embed=embed, view=self)
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, custom_id="prev_simple", disabled=True)
                async def previous_button(self, interaction: discord.Interaction, button: Button):
                    if self.page > 0:
                        self.page -= 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="next_simple")
                async def next_button(self, interaction: discord.Interaction, button: Button):
                    if self.page < self.total_pages - 1:
                        self.page += 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
                async def close_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.edit_message(content="View closed.", embed=None, view=None)
                    self.stop()
            
            # Create initial view
            view = SimplePaginatedView(records)
            await view.update_message(interaction)
            
        except Exception as e:
            print(f"Error in show_simple command: {e}")
            await interaction.followup.send(
                "An error occurred while fetching records.",
                ephemeral=True
            )
    
    async def show_prefix_command(self, ctx: commands.Context):
        """Show all records in the database with pagination (prefix command)"""
        try:
            records = await self._get_all_records()
            
            if not records:
                await ctx.send("No records found in the database.")
                return
            
            # Create paginated view for prefix command
            class PaginatedView(View):
                def __init__(self, records: List[Tuple[str, str]], page: int = 0):
                    super().__init__(timeout=180)
                    self.records = records
                    self.page = page
                    self.records_per_page = 5
                    self.total_pages = (len(records) + self.records_per_page - 1) // self.records_per_page
                    self.original_ctx = ctx
                    self.message = None
                
                async def send_initial(self):
                    # Calculate start and end indices
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    # Create embed
                    embed = discord.Embed(
                        title="Talent Database",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.blue()
                    )
                    
                    # Add records for current page
                    for i in range(start_idx, end_idx):
                        name, wallet = self.records[i]
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    
                    # Update button states
                    for child in self.children:
                        if child.custom_id == "prev_prefix":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next_prefix":
                            child.disabled = self.page == self.total_pages - 1
                    
                    self.message = await self.original_ctx.send(embed=embed, view=self)
                
                async def update_message(self, interaction: discord.Interaction):
                    # Calculate start and end indices
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    # Create embed
                    embed = discord.Embed(
                        title="Talent Database",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.blue()
                    )
                    
                    # Add records for current page
                    for i in range(start_idx, end_idx):
                        name, wallet = self.records[i]
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    
                    # Update button states
                    for child in self.children:
                        if child.custom_id == "prev_prefix":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next_prefix":
                            child.disabled = self.page == self.total_pages - 1
                    
                    await interaction.response.edit_message(embed=embed, view=self)
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, custom_id="prev_prefix", disabled=True)
                async def previous_button(self, interaction: discord.Interaction, button: Button):
                    if self.page > 0:
                        self.page -= 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="next_prefix")
                async def next_button(self, interaction: discord.Interaction, button: Button):
                    if self.page < self.total_pages - 1:
                        self.page += 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
                async def close_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.edit_message(content="View closed.", embed=None, view=None)
                    self.stop()
            
            # Create and send initial view
            view = PaginatedView(records)
            await view.send_initial()
            
        except Exception as e:
            print(f"Error in show prefix command: {e}")
            await ctx.send("An error occurred while fetching records.")
    
    async def show_simple_prefix_command(self, ctx: commands.Context):
        """Show simple list of names and wallets (prefix command)"""
        try:
            records = await self._get_all_records()
            
            if not records:
                await ctx.send("No records found in the database.")
                return
            
            # Create paginated view for simple prefix command
            class SimplePaginatedView(View):
                def __init__(self, records: List[Tuple[str, str]], page: int = 0):
                    super().__init__(timeout=180)
                    self.records = records
                    self.page = page
                    self.records_per_page = 15
                    self.total_pages = (len(records) + self.records_per_page - 1) // self.records_per_page
                    self.original_ctx = ctx
                    self.message = None
                
                async def send_initial(self):
                    # Calculate start and end indices
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    # Create embed
                    embed = discord.Embed(
                        title="Talent Database - Simple View",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.green()
                    )
                    
                    # Add records for current page (in columns)
                    page_records = self.records[start_idx:end_idx]
                    for name, wallet in page_records:
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=True
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    
                    # Update button states
                    for child in self.children:
                        if child.custom_id == "prev_simple_prefix":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next_simple_prefix":
                            child.disabled = self.page == self.total_pages - 1
                    
                    self.message = await self.original_ctx.send(embed=embed, view=self)
                
                async def update_message(self, interaction: discord.Interaction):
                    # Calculate start and end indices
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    # Create embed
                    embed = discord.Embed(
                        title="Talent Database - Simple View",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.green()
                    )
                    
                    # Add records for current page (in columns)
                    page_records = self.records[start_idx:end_idx]
                    for name, wallet in page_records:
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=True
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    
                    # Update button states
                    for child in self.children:
                        if child.custom_id == "prev_simple_prefix":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next_simple_prefix":
                            child.disabled = self.page == self.total_pages - 1
                    
                    await interaction.response.edit_message(embed=embed, view=self)
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, custom_id="prev_simple_prefix", disabled=True)
                async def previous_button(self, interaction: discord.Interaction, button: Button):
                    if self.page > 0:
                        self.page -= 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="next_simple_prefix")
                async def next_button(self, interaction: discord.Interaction, button: Button):
                    if self.page < self.total_pages - 1:
                        self.page += 1
                        await self.update_message(interaction)
                
                @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
                async def close_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.edit_message(content="View closed.", embed=None, view=None)
                    self.stop()
            
            # Create and send initial view
            view = SimplePaginatedView(records)
            await view.send_initial()
            
        except Exception as e:
            print(f"Error in show_simple prefix command: {e}")
            await ctx.send("An error occurred while fetching records.")
    
    async def change_command(self, interaction: discord.Interaction, wallet_address: str, column_name: str, new_value: str):
        """Change a specific field for a wallet address (slash command)"""
        await interaction.response.defer()
        
        valid_columns = [
            'Name', 'Role', 'Injective Role', 'Experience', 'Education',
            'Location', 'Availability', 'Monthly Rate', 'Skills', 'Languages',
            'Discord', 'Email', 'Phone', 'Telegram', 'X', 'Github',
            'Wallet Type', 'NFT Holdings', 'Token Holdings', 'Portfolio',
            'CV', 'Image url', 'Bio', 'Status'
        ]
        
        if column_name not in valid_columns:
            await interaction.followup.send(
                f"Invalid column name. Valid columns are:\n{', '.join(valid_columns)}"
            )
            return
        
        # Check if record exists
        row = await self._find_submission_row(wallet_address)
        if not row:
            await interaction.followup.send(
                f"No record found for wallet address: `{wallet_address}`"
            )
            return
        
        # Get old value for logging
        record = await self._get_record_details(wallet_address)
        if not record:
            await interaction.followup.send(
                "Could not retrieve record details."
            )
            return
        
        old_value = record.get(column_name, "N/A")
        
        # Update the field
        success = await self._update_single_field(wallet_address, column_name, new_value)
        
        if success:
            embed = discord.Embed(
                title="Field Updated Successfully",
                color=discord.Color.green()
            )
            embed.add_field(name="Wallet Address", value=f"`{wallet_address}`", inline=False)
            embed.add_field(name="Field", value=column_name, inline=True)
            embed.add_field(name="Old Value", value=str(old_value)[:100], inline=True)
            embed.add_field(name="New Value", value=str(new_value)[:100], inline=True)
            embed.set_footer(text=f"Updated by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed)
            
            # Also send to submission channel
            try:
                channel = self.bot.get_channel(self.submission_channel_id)
                if channel:
                    admin_embed = discord.Embed(
                        title="Manual Field Update",
                        description=f"Field updated by {interaction.user.mention}",
                        color=discord.Color.orange()
                    )
                    admin_embed.add_field(name="Wallet", value=f"`{wallet_address}`", inline=False)
                    admin_embed.add_field(name="Field", value=column_name, inline=True)
                    admin_embed.add_field(name="Old Value", value=str(old_value)[:50], inline=True)
                    admin_embed.add_field(name="New Value", value=str(new_value)[:50], inline=True)
                    await channel.send(embed=admin_embed)
            except Exception as e:
                print(f"Error notifying channel: {e}")
        else:
            await interaction.followup.send(
                "Failed to update the field. Please check the inputs and try again."
            )
    
    async def change_prefix_command(self, ctx: commands.Context, wallet_address: str, column_name: str, new_value: str):
        """Change a specific field for a wallet address (prefix command)"""
        valid_columns = [
            'Name', 'Role', 'Injective Role', 'Experience', 'Education',
            'Location', 'Availability', 'Monthly Rate', 'Skills', 'Languages',
            'Discord', 'Email', 'Phone', 'Telegram', 'X', 'Github',
            'Wallet Type', 'NFT Holdings', 'Token Holdings', 'Portfolio',
            'CV', 'Image url', 'Bio', 'Status'
        ]
        
        if column_name not in valid_columns:
            await ctx.send(
                f"Invalid column name. Valid columns are:\n{', '.join(valid_columns)}"
            )
            return
        
        # Check if record exists
        row = await self._find_submission_row(wallet_address)
        if not row:
            await ctx.send(f"No record found for wallet address: `{wallet_address}`")
            return
        
        # Get old value for logging
        record = await self._get_record_details(wallet_address)
        if not record:
            await ctx.send("Could not retrieve record details.")
            return
        
        old_value = record.get(column_name, "N/A")
        
        # Send processing message
        processing_msg = await ctx.send("Updating field...")
        
        # Update the field
        success = await self._update_single_field(wallet_address, column_name, new_value)
        
        if success:
            embed = discord.Embed(
                title="Field Updated Successfully",
                color=discord.Color.green()
            )
            embed.add_field(name="Wallet Address", value=f"`{wallet_address}`", inline=False)
            embed.add_field(name="Field", value=column_name, inline=True)
            embed.add_field(name="Old Value", value=str(old_value)[:100], inline=True)
            embed.add_field(name="New Value", value=str(new_value)[:100], inline=True)
            embed.set_footer(text=f"Updated by {ctx.author.name}")
            
            await processing_msg.delete()
            await ctx.send(embed=embed)
            
            # Also send to submission channel
            try:
                channel = self.bot.get_channel(self.submission_channel_id)
                if channel:
                    admin_embed = discord.Embed(
                        title="Manual Field Update",
                        description=f"Field updated by {ctx.author.mention}",
                        color=discord.Color.orange()
                    )
                    admin_embed.add_field(name="Wallet", value=f"`{wallet_address}`", inline=False)
                    admin_embed.add_field(name="Field", value=column_name, inline=True)
                    admin_embed.add_field(name="Old Value", value=str(old_value)[:50], inline=True)
                    admin_embed.add_field(name="New Value", value=str(new_value)[:50], inline=True)
                    await channel.send(embed=admin_embed)
            except Exception as e:
                print(f"Error notifying channel: {e}")
        else:
            await processing_msg.edit(content="Failed to update the field. Please check the inputs and try again.")
    
    async def remove_command(self, interaction: discord.Interaction, wallet_address: str):
        """Remove a record by wallet address (slash command)"""
        await interaction.response.defer()
        
        # Check if record exists
        row = await self._find_submission_row(wallet_address)
        if not row:
            await interaction.followup.send(
                f"No record found for wallet address: `{wallet_address}`"
            )
            return
        
        # Get record details for confirmation
        record = await self._get_record_details(wallet_address)
        if not record:
            await interaction.followup.send(
                "Could not retrieve record details."
            )
            return
        
        # Create confirmation embed
        embed = discord.Embed(
            title="Confirm Deletion",
            description=f"You are about to delete the record for:\n**{record.get('Name', 'Unknown')}**",
            color=discord.Color.red()
        )
        embed.add_field(name="Wallet Address", value=f"`{wallet_address}`", inline=False)
        embed.add_field(name="Role", value=record.get('Role', 'N/A'), inline=True)
        embed.add_field(name="Status", value=record.get('Status', 'N/A'), inline=True)
        embed.set_footer(text="This action cannot be undone!")
        
        # Create confirmation view
        class ConfirmView(View):
            def __init__(self, bot_instance, wallet, is_slash=True):
                super().__init__(timeout=60)
                self.bot_instance = bot_instance
                self.wallet = wallet
                self.is_slash = is_slash
                self.confirmed = False
            
            @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
            async def confirm_delete(self, interaction: discord.Interaction, button: Button):
                self.confirmed = True
                
                # Delete the record
                success = await self.bot_instance._delete_record(self.wallet)
                
                if success:
                    embed = discord.Embed(
                        title="Record Deleted Successfully",
                        description=f"Record for wallet `{self.wallet}` has been deleted.",
                        color=discord.Color.red()
                    )
                    
                    await interaction.response.edit_message(embed=embed, view=None)
                    
                    # Notify submission channel
                    try:
                        channel = self.bot_instance.bot.get_channel(self.bot_instance.submission_channel_id)
                        if channel:
                            admin_embed = discord.Embed(
                                title="Record Deleted",
                                description=f"Record deleted by {interaction.user.mention}",
                                color=discord.Color.red()
                            )
                            admin_embed.add_field(name="Wallet Address", value=f"`{self.wallet}`", inline=False)
                            admin_embed.add_field(name="Name", value=record.get('Name', 'Unknown'), inline=True)
                            await channel.send(embed=admin_embed)
                    except Exception as e:
                        print(f"Error notifying channel: {e}")
                else:
                    await interaction.response.edit_message(
                        content="Failed to delete the record.",
                        embed=None,
                        view=None
                    )
                
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                await interaction.response.edit_message(
                    content="Deletion cancelled.",
                    embed=None,
                    view=None
                )
                self.stop()
        
        view = ConfirmView(self, wallet_address, is_slash=True)
        await interaction.followup.send(embed=embed, view=view)
    
    async def remove_prefix_command(self, ctx: commands.Context, wallet_address: str):
        """Remove a record by wallet address (prefix command)"""
        # Check if record exists
        row = await self._find_submission_row(wallet_address)
        if not row:
            await ctx.send(f"No record found for wallet address: `{wallet_address}`")
            return
        
        # Get record details for confirmation
        record = await self._get_record_details(wallet_address)
        if not record:
            await ctx.send("Could not retrieve record details.")
            return
        
        # Create confirmation embed
        embed = discord.Embed(
            title="Confirm Deletion",
            description=f"You are about to delete the record for:\n**{record.get('Name', 'Unknown')}**",
            color=discord.Color.red()
        )
        embed.add_field(name="Wallet Address", value=f"`{wallet_address}`", inline=False)
        embed.add_field(name="Role", value=record.get('Role', 'N/A'), inline=True)
        embed.add_field(name="Status", value=record.get('Status', 'N/A'), inline=True)
        embed.set_footer(text="This action cannot be undone!")
        
        # Create confirmation view
        class ConfirmView(View):
            def __init__(self, bot_instance, wallet, is_slash=False):
                super().__init__(timeout=60)
                self.bot_instance = bot_instance
                self.wallet = wallet
                self.is_slash = is_slash
                self.confirmed = False
            
            @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
            async def confirm_delete(self, interaction: discord.Interaction, button: Button):
                self.confirmed = True
                
                # Delete the record
                success = await self.bot_instance._delete_record(self.wallet)
                
                if success:
                    embed = discord.Embed(
                        title="Record Deleted Successfully",
                        description=f"Record for wallet `{self.wallet}` has been deleted.",
                        color=discord.Color.red()
                    )
                    
                    await interaction.message.edit(embed=embed, view=None)
                    await interaction.response.send_message("Record deleted!", ephemeral=True)
                    
                    # Notify submission channel
                    try:
                        channel = self.bot_instance.bot.get_channel(self.bot_instance.submission_channel_id)
                        if channel:
                            admin_embed = discord.Embed(
                                title="Record Deleted",
                                description=f"Record deleted by {interaction.user.mention}",
                                color=discord.Color.red()
                            )
                            admin_embed.add_field(name="Wallet Address", value=f"`{self.wallet}`", inline=False)
                            admin_embed.add_field(name="Name", value=record.get('Name', 'Unknown'), inline=True)
                            await channel.send(embed=admin_embed)
                    except Exception as e:
                        print(f"Error notifying channel: {e}")
                else:
                    await interaction.message.edit(
                        content="Failed to delete the record.",
                        embed=None,
                        view=None
                    )
                    await interaction.response.send_message("Failed to delete record.", ephemeral=True)
                
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                await interaction.message.edit(
                    content="Deletion cancelled.",
                    embed=None,
                    view=None
                )
                await interaction.response.send_message("Deletion cancelled.", ephemeral=True)
                self.stop()
        
        view = ConfirmView(self, wallet_address, is_slash=False)
        confirm_msg = await ctx.send(embed=embed, view=view)
    
    # ... (keep the rest of your existing methods the same - from _update_excel_status onwards)
    # The rest of the class remains unchanged from your original code

    async def _update_excel_status(self, wallet_address: str, new_status: str) -> bool:
        try:
            wb = load_workbook(self.excel_file)
            ws = wb.active
            
            row = await self._find_submission_row(wallet_address)
            if not row:
                wb.close()
                return False
            
            ws[f'Z{row}'] = new_status
            wb.save(self.excel_file)
            wb.close()
            return True
            
        except Exception as e:
            print(f"Error updating Excel status: {e}")
            return False
    
    async def _update_excel_record(self, wallet_address: str, updates: dict, status: str) -> bool:
        try:
            wb = load_workbook(self.excel_file)
            ws = wb.active
            
            row = await self._find_submission_row(wallet_address)
            if not row:
                wb.close()
                return False
            
            column_map = {
                'name': 'A',
                'role': 'B',
                'injectiveRole': 'C',
                'experience': 'D',
                'education': 'E',
                'location': 'F',
                'available': 'G',
                'monthlyRate': 'H',
                'skills': 'I',
                'languages': 'J',
                'discord': 'K',
                'email': 'L',
                'phone': 'M',
                'telegram': 'N',
                'X': 'O',
                'github': 'P',
                'walletType': 'R',
                'nftHold': 'S',
                'tokenHold': 'T',
                'portfolio': 'U',
                'cv': 'V',
                'profilePicture': 'W',
                'bio': 'X'
            }
            
            for field, value in updates.items():
                if field in column_map:
                    col = column_map[field]
                    if field == 'available':
                        ws[f'{col}{row}'] = 'Yes' if value else 'No'
                    elif field in ['skills', 'languages']:
                        ws[f'{col}{row}'] = ', '.join(value) if isinstance(value, list) else value
                    else:
                        ws[f'{col}{row}'] = str(value).strip() if value else ''
            
            ws[f'Y{row}'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ws[f'Z{row}'] = status
            
            wb.save(self.excel_file)
            wb.close()
            return True
            
        except Exception as e:
            print(f"Error updating Excel record: {e}")
            return False
    
    async def _get_existing_record(self, wallet_address: str) -> Optional[dict]:
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            row = await self._find_submission_row(wallet_address)
            if not row:
                wb.close()
                return None
            
            record = {
                'name': ws[f'A{row}'].value,
                'role': ws[f'B{row}'].value,
                'injectiveRole': ws[f'C{row}'].value,
                'experience': ws[f'D{row}'].value,
                'education': ws[f'E{row}'].value,
                'location': ws[f'F{row}'].value,
                'available': ws[f'G{row}'].value == 'Yes',
                'monthlyRate': ws[f'H{row}'].value,
                'skills': ws[f'I{row}'].value.split(', ') if ws[f'I{row}'].value else [],
                'languages': ws[f'J{row}'].value.split(', ') if ws[f'J{row}'].value else [],
                'discord': ws[f'K{row}'].value,
                'email': ws[f'L{row}'].value,
                'phone': ws[f'M{row}'].value,
                'telegram': ws[f'N{row}'].value,
                'X': ws[f'O{row}'].value,
                'github': ws[f'P{row}'].value,
                'walletAddress': ws[f'Q{row}'].value,
                'walletType': ws[f'R{row}'].value,
                'nftHold': ws[f'S{row}'].value,
                'tokenHold': ws[f'T{row}'].value,
                'portfolio': ws[f'U{row}'].value,
                'cv': ws[f'V{row}'].value,
                'profilePicture': ws[f'W{row}'].value,
                'bio': ws[f'X{row}'].value,
                'status': ws[f'Z{row}'].value
            }
            
            wb.close()
            return record
            
        except Exception as e:
            print(f"Error reading record from Excel: {e}")
            return None
    
    async def _save_new_submission(self, data: dict) -> bool:
        try:
            wallet = data.get('walletAddress', '')
            
            row = [
                data.get('name', '').strip(),
                data.get('role', '').strip(),
                data.get('injectiveRole', '').strip(),
                data.get('experience', '').strip(),
                data.get('education', '').strip(),
                data.get('location', '').strip(),
                'Yes' if data.get('available', False) else 'No',
                data.get('monthlyRate', '').strip(),
                ', '.join(data.get('skills', [])),
                ', '.join(data.get('languages', [])),
                data.get('discord', '').strip(),
                data.get('email', '').strip(),
                data.get('phone', '').strip() or '-',
                data.get('telegram', '').strip() or '-',
                data.get('X', '').strip() or '-',
                data.get('github', '').strip() or '-',
                wallet,
                data.get('walletType', '').strip(),
                data.get('nftHold', '').strip(),
                data.get('tokenHold', '').strip(),
                data.get('portfolio', '').strip() or '-',
                data.get('cv', '').strip(),
                data.get('profilePicture', '').strip(),
                data.get('bio', '').strip(),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "Pending"
            ]
            
            wb = load_workbook(self.excel_file)
            ws = wb.active
            ws.append(row)
            wb.save(self.excel_file)
            wb.close()
            return True
            
        except Exception as e:
            print(f"Error saving submission to Excel: {e}")
            return False
    
    async def on_ready(self):
        print(f'Bot logged in as {self.bot.user}')
        try:
            synced = await self.bot.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Error syncing commands: {e}")
    
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
            
        try:
            custom_id = interaction.data.get('custom_id', '')
            if ':' not in custom_id:
                return
                
            action_type, action, wallet = custom_id.split(':', 2)
            
            if action_type == "submission":
                await self._handle_submission_interaction(interaction, action, wallet)
            elif action_type == "update":
                await self._handle_update_interaction(interaction, action, wallet)
                
        except ValueError:
            try:
                action, wallet = custom_id.split(':', 1)
                await self._handle_submission_interaction(interaction, action, wallet)
            except:
                return
        except Exception as e:
            print(f"Error handling interaction: {e}")
            await interaction.response.send_message(
                "An error occurred while processing your request!",
                ephemeral=True
            )
    
    async def _handle_submission_interaction(self, interaction: discord.Interaction, action: str, wallet: str):
        submission = self.pending_submissions.get(wallet)
        
        if not submission:
            await interaction.response.send_message(
                "Submission not found or already processed!",
                ephemeral=True
            )
            return
            
        if action == "approve":
            submission['status'] = "Approved"
            success = await self._update_excel_status(wallet, "Approved")
            await self._update_submission_message(interaction, submission)
            
            if success:
                await interaction.response.send_message(
                    "Submission approved and Excel updated!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Approved but failed to update Excel!",
                    ephemeral=True
                )
                
        elif action == "reject":
            submission['status'] = "Rejected"
            success = await self._update_excel_status(wallet, "Rejected")
            await self._update_submission_message(interaction, submission)
            
            if success:
                await interaction.response.send_message(
                    "Submission rejected and Excel updated!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Rejected but failed to update Excel!",
                    ephemeral=True
                )
                
        elif action == "changes":
            await interaction.response.send_modal(
                SubmissionChangesModal(submission))
    
    async def _handle_update_interaction(self, interaction: discord.Interaction, action: str, wallet: str):
        update_data = self.pending_updates.get(wallet)
        
        if not update_data:
            await interaction.response.send_message(
                "Update not found or already processed!",
                ephemeral=True
            )
            return
            
        if action == "approve":
            success = await self._update_excel_record(wallet, update_data['updates'], "Approved")
            await self._update_update_message(interaction, update_data, "Approved")
            
            if success:
                await interaction.response.send_message(
                    "Update approved and Excel updated!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Approved but failed to update Excel!",
                    ephemeral=True
                )
                
        elif action == "reject":
            await self._update_excel_record(wallet, {}, "Rejected")
            await self._update_update_message(interaction, update_data, "Rejected")
            await interaction.response.send_message(
                "Update rejected - Status updated in Excel",
                ephemeral=True
            )
                
        elif action == "changes":
            await interaction.response.send_modal(
                UpdateChangesModal(update_data))
    
    async def _update_submission_message(self, interaction: discord.Interaction, submission: dict):
        try:
            embed = self._create_submission_embed(submission)
            message = await interaction.channel.fetch_message(submission['message_id'])
            await message.edit(embed=embed, view=None)
        except Exception as e:
            print(f"Error updating submission message: {e}")
    
    async def _update_update_message(self, interaction: discord.Interaction, update_data: dict, status: str):
        """Update the Discord message for an update"""
        try:
            embed = self._create_update_embed(update_data, status)
            message = await interaction.channel.fetch_message(update_data['message_id'])
            await message.edit(embed=embed, view=None)
        except Exception as e:
            print(f"Error updating update message: {e}")
    
    def _create_submission_embed(self, data: dict) -> discord.Embed:
        submission_data = data.get('data', {})
        status = data.get('status', 'Pending')
        
        color_map = {
            "Approved": 0x00ff00,    
            "Rejected": 0xff0000,    
            "Pending": 0xffff00,     
            "Changes Requested": 0xffa500,
            "On Hold": 0x808080       
        }
        color = color_map.get(status, 0xffff00)
        
        embed = discord.Embed(
            title=f"{submission_data.get('name', 'N/A')} - {status}",
            description=f"**{submission_data.get('role', 'N/A')}** | {submission_data.get('injectiveRole', 'N/A')}",
            color=color
        )
        
        if submission_data.get('profilePicture'):
            embed.set_thumbnail(url=submission_data['profilePicture'])
        
        basic_info = [
            f"**Experience:** {submission_data.get('experience', 'N/A')}",
            f"**Education:** {submission_data.get('education', 'N/A')}",
            f"**Location:** {submission_data.get('location', 'N/A')}",
            f"**Availability:** {'Yes' if submission_data.get('available') else 'No'}",
            f"**Rate:** {submission_data.get('monthlyRate', 'N/A')}",
            f"**Wallet:** `{data.get('wallet', 'N/A')[:6]}...{data.get('wallet', 'N/A')[-4:]}`"
        ]
        embed.add_field(name="Basic Info", value="\n".join(basic_info), inline=False)
        
        blockchain_info = [
            f"**NFTs:** {submission_data.get('nftHold', 'N/A')}",
            f"**Tokens:** {submission_data.get('tokenHold', 'N/A')}",
            f"**Wallet Type:** {submission_data.get('walletType', 'N/A')}"
        ]
        embed.add_field(name="Blockchain Info", value="\n".join(blockchain_info), inline=False)
        
        skills = "• " + "\n• ".join(submission_data.get('skills', [])) if submission_data.get('skills') else "None"
        languages = "• " + "\n• ".join(submission_data.get('languages', [])) if submission_data.get('languages') else "None"
        embed.add_field(name="Skills", value=skills, inline=True)
        embed.add_field(name="Languages", value=languages, inline=True)
        
        contact_info = [
            f"**Discord:** {submission_data.get('discord', '-')}",
            f"**Email:** {submission_data.get('email', '-')}",
            f"**Phone:** {submission_data.get('phone', '-')}",
            f"**Telegram:** {submission_data.get('telegram', 'N/A') or '-'}",
            f"**X:** {submission_data.get('X', 'N/A') or '-'}",
            f"**GitHub:** {submission_data.get('github', 'N/A') or '-'}"
        ]
        embed.add_field(name="Contact Info", value="\n".join(contact_info), inline=False)
        
        links = []
        if submission_data.get('portfolio'):
            links.append(f"**Portfolio:** {submission_data['portfolio']}")
        if submission_data.get('cv'):
            links.append(f"**CV:** [Download CV]({submission_data['cv']})")
        if links:
            embed.add_field(name="Links", value="\n".join(links), inline=False)
        
        bio = submission_data.get('bio', 'No bio provided')
        embed.add_field(
            name="Bio", 
            value=f"{bio[:250]}{'...' if len(bio) > 250 else ''}", 
            inline=False
        )
        
        embed.set_footer(text=f"Submitted on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return embed
    
    def _create_update_embed(self, update_data: dict, status: str) -> discord.Embed:
        existing_data = update_data.get('existing_data', {})
        updates = update_data.get('updates', {})
        wallet = update_data.get('wallet', '')
        
        color_map = {
            "Approved": 0x00ff00,    
            "Rejected": 0xff0000,    
            "Pending": 0xffff00,     
            "Changes Requested": 0xffa500
        }
        color = color_map.get(status, 0xffff00)
        
        embed = discord.Embed(
            title=f"Talent Profile Update - {status}",
            description=f"**{existing_data.get('name', 'N/A')}** | `{wallet[:6]}...{wallet[-4:]}`",
            color=color
        )
        
        if existing_data.get('profilePicture'):
            embed.set_thumbnail(url=existing_data['profilePicture'])
        
        current_field = {"name": "Proposed Changes", "value": "", "inline": False}
        
        for field, new_value in updates.items():
            old_value = existing_data.get(field, '')
            
            if field == 'available':
                old_value = 'Yes' if old_value else 'No'
                new_value = 'Yes' if new_value else 'No'
            elif field in ['skills', 'languages']:
                old_value = ', '.join(old_value) if isinstance(old_value, list) else old_value
                new_value = ', '.join(new_value) if isinstance(new_value, list) else new_value
            
            entry = (
                f"**{field.capitalize()}:**\n"
                f"`Old:` {old_value}\n"
                f"`New:` {new_value}\n\n"
            )
            
            if len(current_field["value"]) + len(entry) > 1024:
                embed.add_field(**current_field)
                current_field = {
                    "name": "Proposed Changes (cont.)",
                    "value": entry,
                    "inline": False
                }
            else:
                current_field["value"] += entry
        
        if current_field["value"] or not updates:
            if not updates:
                current_field["value"] = "No specific changes - renewal only"
            embed.add_field(**current_field)
        
        embed.set_footer(text=f"Update requested on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return embed
    
    def _create_submission_review_buttons(self, wallet: str) -> View:
        view = View(timeout=None)  
        
        buttons = [
            Button(label="Approve", style=discord.ButtonStyle.success, custom_id=f"submission:approve:{wallet}"),
            Button(label="Reject", style=discord.ButtonStyle.danger, custom_id=f"submission:reject:{wallet}"),
            Button(label="Request Changes", style=discord.ButtonStyle.primary, custom_id=f"submission:changes:{wallet}")
        ]
        
        for button in buttons:
            view.add_item(button)
            
        return view
    
    def _create_update_review_buttons(self, wallet: str) -> View:
        view = View(timeout=None)  
        
        buttons = [
            Button(label="Approve", style=discord.ButtonStyle.success, custom_id=f"update:approve:{wallet}"),
            Button(label="Reject", style=discord.ButtonStyle.danger, custom_id=f"update:reject:{wallet}"),
        ]
        
        for button in buttons:
            view.add_item(button)
            
        return view
    
    async def post_submission(self, data: dict) -> Optional[discord.Message]:
        try:
            channel = self.bot.get_channel(self.submission_channel_id)
            if not channel:
                print("Error: Submission channel not found!")
                return None
                
            wallet = data['walletAddress']
            submission = {
                'data': data,
                'status': "Pending",
                'wallet': wallet
            }
            
            excel_success = await self._save_new_submission(data)
            if not excel_success:
                print(f"Warning: Failed to save submission for {wallet} to Excel")
                
            self.pending_submissions[wallet] = submission
            
            embed = self._create_submission_embed(submission)
            view = self._create_submission_review_buttons(wallet)
            
            message = await channel.send(embed=embed, view=view)
            submission['message_id'] = message.id
            
            return message
            
        except Exception as e:
            print(f"Error posting submission: {e}")
            return None
    
    async def post_update_request(self, wallet_address: str, updates: dict) -> Optional[discord.Message]:
        try:
            channel = self.bot.get_channel(self.submission_channel_id)
            if not channel:
                print("Error: Submission channel not found!")
                return None
                
            existing_data = await self._get_existing_record(wallet_address)
            if not existing_data:
                print(f"Error: No existing record found for wallet {wallet_address}")
                return None
                
            update_data = {
                'existing_data': existing_data,
                'updates': updates,
                'wallet': wallet_address,
                'status': "Pending"
            }
            
            self.pending_updates[wallet_address] = update_data
            
            embed = self._create_update_embed(update_data, "Pending")
            view = self._create_update_review_buttons(wallet_address)
            
            message = await channel.send(embed=embed, view=view)
            update_data['message_id'] = message.id
            
            return message
            
        except Exception as e:
            print(f"Error posting update request: {e}")
            return None
    
    def start(self):
        """Start the bot"""
        self.bot.run(self.bot_code)


class SubmissionChangesModal(Modal, title="Edit Submission"):
    def __init__(self, submission: dict):
        super().__init__()
        self.submission = submission
        submission_data = submission['data']
        
        self.name = TextInput(
            label="Name",
            default=submission_data.get('name', ''),
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.name)
        
        self.role = TextInput(
            label="Role",
            default=submission_data.get('role', ''),
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.role)
        
        self.injective_role = TextInput(
            label="Injective Role",
            default=submission_data.get('injectiveRole', ''),
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.injective_role)
        
        self.experience = TextInput(
            label="Experience",
            default=submission_data.get('experience', ''),
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.experience)
        
        self.education = TextInput(
            label="Education",
            default=submission_data.get('education', ''),
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.education)
        
    async def on_submit(self, interaction: discord.Interaction):
        submission_data = self.submission['data']
        
        submission_data.update({
            'name': self.name.value,
            'role': self.role.value,
            'injectiveRole': self.injective_role.value,
            'experience': self.experience.value,
            'education': self.education.value
        })
        
        self.submission['status'] = "Approved"
        wallet = self.submission['wallet']
        success = await TalentHubBot()._update_excel_status(wallet, "Approved")
        
        await TalentHubBot()._update_submission_message(interaction, self.submission)
        
        if success:
            await interaction.response.send_message(
                "Changes saved and submission approved! Excel updated.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Changes saved and approved but failed to update Excel!",
                ephemeral=True
            )


class UpdateChangesModal(Modal, title="Edit Update Request"):
    def __init__(self, update_data: dict):
        super().__init__()
        self.update_data = update_data
        
        self.notes = TextInput(
            label="Changes Requested",
            placeholder="Specify what changes are needed...",
            required=True,
            style=discord.TextStyle.long
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        success = await TalentHubBot()._update_excel_record(
            self.update_data['wallet'], 
            {}, 
            "Changes Requested"
        )
        
        wallet = self.update_data['wallet']
        self.update_data['status'] = "Changes Requested"
        
        await TalentHubBot()._update_update_message(interaction, self.update_data, "Changes Requested")
        
        try:
            submitter = await interaction.guild.fetch_member(int(wallet)) 
            if submitter:
                await submitter.send(
                    f"Your talent profile update for wallet `{wallet[:6]}...{wallet[-4:]}` requires changes:\n"
                    f"```{self.notes.value}```\n"
                    "Please submit a new update with the requested changes."
                )
        except Exception as e:
            print(f"Couldn't notify submitter: {e}")
        
        if success:
            await interaction.response.send_message(
                "Changes requested and status updated in Excel!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Changes requested but failed to update Excel status!",
                ephemeral=True
            )


talent_hub_bot = TalentHubBot()

if __name__ == "__main__":
    talent_hub_bot.start()