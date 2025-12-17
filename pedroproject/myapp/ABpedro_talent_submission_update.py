import os
import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from openpyxl import Workbook, load_workbook
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Any
from dotenv import load_dotenv
import traceback
import queue as thread_queue

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
        intents = discord.Intents.default()
        intents.message_content = True
        
        self.bot = commands.Bot(
            command_prefix="!", 
            intents=intents,
            max_messages=None
        )
        self.submission_channel_id = 1374018261578027129
        self.pending_submissions: Dict[str, dict] = {}
        self.pending_updates: Dict[str, dict] = {}
        self.excel_file = "Atalent_submissions.xlsx"
        self.bot_code = os.getenv("DISCORD_BOT")
        
        if not self.bot_code:
            print("❌ ERROR: DISCORD_BOT token not found in environment variables!")
            print("💡 Make sure you have a .env file with: DISCORD_BOT=your_bot_token_here")
            return
        
        # Initialize the lock for thread safety
        self._lock = asyncio.Lock()
        
        # Thread-safe queue for submissions from other threads
        self._thread_submission_queue = thread_queue.Queue()
        self._queue_processing = False
        
        self._ensure_excel_file()
        
        # Set up bot events
        self.bot.event(self.on_ready)
        self.bot.event(self.on_interaction)
        
        # Register slash commands
        self.bot.tree.command(name="job_show")(self.show_command)
        self.bot.tree.command(name="job_change")(self.change_command)
        self.bot.tree.command(name="job_remove")(self.remove_command)
        self.bot.tree.command(name="job_variable")(self.column_names_command)
        
        # Register prefix commands
        @self.bot.command(name="job_show")
        async def show_prefix(ctx):
            await self.show_prefix_command(ctx)
            
        @self.bot.command(name="job_change")
        async def change_prefix(ctx, wallet_address: str, column_name: str, *, new_value: str):
            await self.change_prefix_command(ctx, wallet_address, column_name, new_value)
            
        @self.bot.command(name="job_remove")
        async def remove_prefix(ctx, wallet_address: str):
            await self.remove_prefix_command(ctx, wallet_address)
            
        @self.bot.command(name="job_variable")
        async def column_names_prefix(ctx):
            await self.column_names_prefix_command(ctx)
    
    def _ensure_excel_file(self):
        """Ensure the Excel file exists with correct headers"""
        if not os.path.exists(self.excel_file):
            print(f"📄 Creating new Excel file: {self.excel_file}")
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
                actual_headers = [cell.value for cell in ws[1]]
                if actual_headers != expected_headers:
                    print(f"📄 Excel headers mismatch. Recreating file...")
                    os.remove(self.excel_file)
                    self._init_excel_file()
                wb.close()
            except Exception as e:
                print(f"❌ Error verifying Excel file: {e}")
                if os.path.exists(self.excel_file):
                    os.remove(self.excel_file)
                self._init_excel_file()
    
    def _init_excel_file(self):
        """Initialize a new Excel file with headers"""
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
        print(f"✅ Initialized Excel file with headers")
    
    async def _find_submission_row(self, wallet_address: str) -> Optional[int]:
        """Find the row number for a wallet address in Excel"""
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            for row in range(2, ws.max_row + 1):
                cell_value = ws[f'Q{row}'].value
                if cell_value and str(cell_value).lower() == wallet_address.lower():
                    wb.close()
                    return row
            
            wb.close()
            return None
            
        except Exception as e:
            print(f"❌ Error searching Excel file: {e}")
            return None
    
    async def _get_all_records(self) -> List[Tuple[str, str]]:
        """Get all wallet addresses and names from Excel"""
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
            print(f"❌ Error getting all records: {e}")
            return []
    
    async def _get_all_records_with_details(self) -> List[dict]:
        """Get all records with detailed information"""
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            records = []
            for row in range(2, ws.max_row + 1):
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
            print(f"❌ Error getting all records with details: {e}")
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
            
            ws.delete_rows(row)
            wb.save(self.excel_file)
            wb.close()
            return True
            
        except Exception as e:
            print(f"❌ Error deleting record: {e}")
            return False
    
    async def _update_single_field(self, wallet_address: str, column_name: str, new_value: str) -> bool:
        """Update a single field in a record"""
        try:
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
            
            col = column_map[column_name]
            ws[f'{col}{row}'] = new_value
            
            ws[f'Y{row}'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            wb.save(self.excel_file)
            wb.close()
            return True
            
        except Exception as e:
            print(f"❌ Error updating field: {e}")
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
            print(f"❌ Error getting record details: {e}")
            return None
    
    async def column_names_command(self, interaction: discord.Interaction):
        """Show all available variables in the database (slash command)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            valid_columns = [
                'Name', 'Role', 'Injective Role', 'Experience', 'Education',
                'Location', 'Availability', 'Monthly Rate', 'Skills', 'Languages',
                'Discord', 'Email', 'Phone', 'Telegram', 'X', 'Github',
                'Wallet Type', 'NFT Holdings', 'Token Holdings', 'Portfolio',
                'CV', 'Image url', 'Bio', 'Status'
            ]
            
            embed = discord.Embed(
                title="Available Column Names",
                description="These are the columns you can modify using the /change command:",
                color=discord.Color.blue()
            )
            
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
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Error in column_names command: {e}")
            traceback.print_exc()
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
            
            embed = discord.Embed(
                title="Available Column Names",
                description="These are the columns you can modify using the !change command:",
                color=discord.Color.blue()
            )
            
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
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Error in column_names prefix command: {e}")
            await ctx.send("An error occurred while fetching column names.")
    
    async def show_command(self, interaction: discord.Interaction):
        """Show all records in the database with pagination (slash command)"""
        await interaction.response.defer()
        
        try:
            records = await self._get_all_records()
            
            if not records:
                await interaction.followup.send("No records found in the database.")
                return
            
            class PaginatedView(View):
                def __init__(self, records: List[Tuple[str, str]], page: int = 0):
                    super().__init__(timeout=180)
                    self.records = records
                    self.page = page
                    self.records_per_page = 5
                    self.total_pages = (len(records) + self.records_per_page - 1) // self.records_per_page
                
                def create_embed(self):
                    """Create embed for current page"""
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    embed = discord.Embed(
                        title="Talent Database",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.blue()
                    )
                    
                    for i in range(start_idx, end_idx):
                        name, wallet = self.records[i]
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    return embed
                
                async def update_buttons(self):
                    """Update button states"""
                    for child in self.children:
                        if child.custom_id == "prev":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next":
                            child.disabled = self.page == self.total_pages - 1
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, custom_id="prev", disabled=True)
                async def previous_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.defer()
                    if self.page > 0:
                        self.page -= 1
                        embed = self.create_embed()
                        await self.update_buttons()
                        await interaction.edit_original_response(embed=embed, view=self)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="next")
                async def next_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.defer()
                    if self.page < self.total_pages - 1:
                        self.page += 1
                        embed = self.create_embed()
                        await self.update_buttons()
                        await interaction.edit_original_response(embed=embed, view=self)
                
                @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
                async def close_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.defer()
                    await interaction.edit_original_response(content="View closed.", embed=None, view=None)
                    self.stop()
            
            view = PaginatedView(records)
            
            embed = view.create_embed()
            await view.update_buttons()
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ Error in show command: {e}")
            traceback.print_exc()
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
            
            class PaginatedView(View):
                def __init__(self, records: List[Tuple[str, str]], page: int = 0):
                    super().__init__(timeout=180)
                    self.records = records
                    self.page = page
                    self.records_per_page = 5
                    self.total_pages = (len(records) + self.records_per_page - 1) // self.records_per_page
                
                def create_embed(self):
                    """Create embed for current page"""
                    start_idx = self.page * self.records_per_page
                    end_idx = min(start_idx + self.records_per_page, len(self.records))
                    
                    embed = discord.Embed(
                        title="Talent Database",
                        description=f"Showing records {start_idx + 1}-{end_idx} of {len(self.records)}",
                        color=discord.Color.blue()
                    )
                    
                    for i in range(start_idx, end_idx):
                        name, wallet = self.records[i]
                        embed.add_field(
                            name=f"{name}",
                            value=f"`{wallet}`",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Use buttons to navigate")
                    return embed
                
                async def update_buttons(self):
                    """Update button states"""
                    for child in self.children:
                        if child.custom_id == "prev_prefix":
                            child.disabled = self.page == 0
                        elif child.custom_id == "next_prefix":
                            child.disabled = self.page == self.total_pages - 1
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, custom_id="prev_prefix", disabled=True)
                async def previous_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.defer()
                    if self.page > 0:
                        self.page -= 1
                        embed = self.create_embed()
                        await self.update_buttons()
                        await interaction.edit_original_response(embed=embed, view=self)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="next_prefix")
                async def next_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.defer()
                    if self.page < self.total_pages - 1:
                        self.page += 1
                        embed = self.create_embed()
                        await self.update_buttons()
                        await interaction.edit_original_response(embed=embed, view=self)
                
                @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
                async def close_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.defer()
                    await interaction.edit_original_response(content="View closed.", embed=None, view=None)
                    self.stop()
            
            view = PaginatedView(records)
            embed = view.create_embed()
            await view.update_buttons()
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ Error in show prefix command: {e}")
            traceback.print_exc()
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
        
        row = await self._find_submission_row(wallet_address)
        if not row:
            await interaction.followup.send(
                f"No record found for wallet address: `{wallet_address}`"
            )
            return
        
        record = await self._get_record_details(wallet_address)
        if not record:
            await interaction.followup.send(
                "Could not retrieve record details."
            )
            return
        
        old_value = record.get(column_name, "N/A")
        
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
                print(f"❌ Error notifying channel: {e}")
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
        
        row = await self._find_submission_row(wallet_address)
        if not row:
            await ctx.send(f"No record found for wallet address: `{wallet_address}`")
            return
        
        record = await self._get_record_details(wallet_address)
        if not record:
            await ctx.send("Could not retrieve record details.")
            return
        
        old_value = record.get(column_name, "N/A")
        
        processing_msg = await ctx.send("Updating field...")
        
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
                print(f"❌ Error notifying channel: {e}")
        else:
            await processing_msg.edit(content="Failed to update the field. Please check the inputs and try again.")
    
    async def remove_command(self, interaction: discord.Interaction, wallet_address: str):
        """Remove a record by wallet address (slash command)"""
        await interaction.response.defer()
        
        row = await self._find_submission_row(wallet_address)
        if not row:
            await interaction.followup.send(
                f"No record found for wallet address: `{wallet_address}`"
            )
            return
        
        record = await self._get_record_details(wallet_address)
        if not record:
            await interaction.followup.send(
                "Could not retrieve record details."
            )
            return
        
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
                await interaction.response.defer()
                self.confirmed = True
                
                # Delete the record
                success = await self.bot_instance._delete_record(self.wallet)
                
                if success:
                    embed = discord.Embed(
                        title="Record Deleted Successfully",
                        description=f"Record for wallet `{self.wallet}` has been deleted.",
                        color=discord.Color.red()
                    )
                    
                    await interaction.edit_original_response(embed=embed, view=None)
                    
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
                        print(f"❌ Error notifying channel: {e}")
                else:
                    await interaction.edit_original_response(
                        content="Failed to delete the record.",
                        embed=None,
                        view=None
                    )
                
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                await interaction.response.defer()
                await interaction.edit_original_response(
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
                await interaction.response.defer()
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
                        print(f"❌ Error notifying channel: {e}")
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
                await interaction.response.defer()
                await interaction.message.edit(
                    content="Deletion cancelled.",
                    embed=None,
                    view=None
                )
                await interaction.response.send_message("Deletion cancelled.", ephemeral=True)
                self.stop()
        
        view = ConfirmView(self, wallet_address, is_slash=False)
        confirm_msg = await ctx.send(embed=embed, view=view)
    
    async def _save_new_submission(self, data: dict) -> bool:
        """Save a new submission to Excel"""
        try:
            wallet = data.get('walletAddress', '')
            
            # Check if already exists
            existing_row = await self._find_submission_row(wallet)
            if existing_row:
                print(f"⚠️ Wallet {wallet} already exists in row {existing_row}. Updating instead.")
                return await self._update_existing_submission(data, existing_row)
            
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
            print(f"✅ Saved new submission to Excel for wallet: {wallet}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving submission to Excel: {e}")
            traceback.print_exc()
            return False
    
    async def _update_existing_submission(self, data: dict, row: int) -> bool:
        """Update an existing submission in Excel"""
        try:
            wb = load_workbook(self.excel_file)
            ws = wb.active
            
            # Update the existing row
            ws[f'A{row}'] = data.get('name', '').strip()
            ws[f'B{row}'] = data.get('role', '').strip()
            ws[f'C{row}'] = data.get('injectiveRole', '').strip()
            ws[f'D{row}'] = data.get('experience', '').strip()
            ws[f'E{row}'] = data.get('education', '').strip()
            ws[f'F{row}'] = data.get('location', '').strip()
            ws[f'G{row}'] = 'Yes' if data.get('available', False) else 'No'
            ws[f'H{row}'] = data.get('monthlyRate', '').strip()
            ws[f'I{row}'] = ', '.join(data.get('skills', []))
            ws[f'J{row}'] = ', '.join(data.get('languages', []))
            ws[f'K{row}'] = data.get('discord', '').strip()
            ws[f'L{row}'] = data.get('email', '').strip()
            ws[f'M{row}'] = data.get('phone', '').strip() or '-'
            ws[f'N{row}'] = data.get('telegram', '').strip() or '-'
            ws[f'O{row}'] = data.get('X', '').strip() or '-'
            ws[f'P{row}'] = data.get('github', '').strip() or '-'
            ws[f'R{row}'] = data.get('walletType', '').strip()
            ws[f'S{row}'] = data.get('nftHold', '').strip()
            ws[f'T{row}'] = data.get('tokenHold', '').strip()
            ws[f'U{row}'] = data.get('portfolio', '').strip() or '-'
            ws[f'V{row}'] = data.get('cv', '').strip()
            ws[f'W{row}'] = data.get('profilePicture', '').strip()
            ws[f'X{row}'] = data.get('bio', '').strip()
            ws[f'Y{row}'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ws[f'Z{row}'] = "Pending"  # Reset status to Pending for updates
            
            wb.save(self.excel_file)
            wb.close()
            print(f"✅ Updated existing submission in Excel for row: {row}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating existing submission: {e}")
            traceback.print_exc()
            return False
    
    async def on_ready(self):
        """Called when bot is ready and connected to Discord"""
        print(f'✅ Bot logged in as {self.bot.user}')
        print(f'✅ Bot ID: {self.bot.user.id}')
        print(f'✅ Submission channel ID: {self.submission_channel_id}')
        
        # Check channel access
        channel = self.bot.get_channel(self.submission_channel_id)
        if channel:
            print(f'✅ Found submission channel: #{channel.name} ({channel.id})')
            permissions = channel.permissions_for(channel.guild.me)
            print(f'✅ Bot permissions in channel:')
            print(f'   - Send Messages: {permissions.send_messages}')
            print(f'   - Embed Links: {permissions.embed_links}')
            print(f'   - Read Messages: {permissions.read_messages}')
        else:
            print(f'❌ Cannot find channel with ID {self.submission_channel_id}')
            print('💡 Make sure:')
            print('   1. The bot is added to your Discord server')
            print('   2. The channel ID is correct')
            print('   3. The bot has permission to view the channel')
        
        try:
            # Sync commands globally
            synced = await self.bot.tree.sync()
            print(f"✅ Synced {len(synced)} command(s)")
            
            # Start the queue processor
            asyncio.create_task(self._process_submission_queue())
            print("✅ Started submission queue processor")
            
        except Exception as e:
            print(f"❌ Error syncing commands: {e}")
            traceback.print_exc()
    
    async def _process_submission_queue(self):
        """Process submissions from the thread-safe queue"""
        print("🔄 Submission queue processor started")
        while True:
            try:
                # Check if there are submissions in the queue
                if not self._thread_submission_queue.empty():
                    # Get all pending submissions
                    pending = []
                    while not self._thread_submission_queue.empty():
                        try:
                            submission = self._thread_submission_queue.get_nowait()
                            pending.append(submission)
                            print(f"[QUEUE] Got submission from queue for: {submission.get('walletAddress', 'Unknown')}")
                        except thread_queue.Empty:
                            break
                    
                    # Process each submission
                    for data in pending:
                        try:
                            print(f"[QUEUE] Processing submission for: {data.get('walletAddress', 'Unknown')}")
                            await self._process_submission_directly(data)
                        except Exception as e:
                            print(f"[QUEUE ERROR] Error processing submission: {e}")
                            traceback.print_exc()
                
                # Sleep to prevent busy waiting
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"[QUEUE ERROR] Error in queue processor: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_submission_directly(self, data: dict) -> Optional[discord.Message]:
        """Internal method to process a submission"""
        try:
            print(f"[DIRECT] Starting submission for wallet: {data.get('walletAddress', 'Unknown')}")
            
            # Check if bot is ready
            if not hasattr(self, 'bot') or not self.bot.is_ready():
                print("[DIRECT] Bot not ready, re-queuing submission...")
                # Re-add to queue for later processing
                self._thread_submission_queue.put(data)
                return None
            
            # Validate required fields
            required_fields = ['walletAddress', 'name', 'role']
            for field in required_fields:
                if field not in data:
                    print(f"[DIRECT ERROR] Missing required field: {field}")
                    return None
            
            wallet = data['walletAddress']
            
            # Check for duplicate pending submissions with lock
            async with self._lock:
                if wallet in self.pending_submissions:
                    print(f"[DIRECT WARNING] Duplicate submission already pending for {wallet}")
                    return None
            
            # Get channel
            channel = self.bot.get_channel(self.submission_channel_id)
            if not channel:
                print(f"[DIRECT ERROR] Submission channel {self.submission_channel_id} not found!")
                # List available channels for debugging
                text_channels = [c for c in self.bot.get_all_channels() if isinstance(c, discord.TextChannel)]
                print(f"[DIRECT ERROR] Available text channels: {[f'#{c.name} ({c.id})' for c in text_channels[:5]]}")
                return None
                
            # Check permissions
            bot_member = channel.guild.me
            permissions = channel.permissions_for(bot_member)
            
            if not permissions.send_messages:
                print("[DIRECT ERROR] Bot doesn't have permission to send messages in this channel!")
                return None
            
            if not permissions.embed_links:
                print("[DIRECT ERROR] Bot doesn't have permission to embed links in this channel!")
                return None
            
            # Create submission object
            submission = {
                'data': data,
                'status': "Pending",
                'wallet': wallet,
                'timestamp': datetime.now().isoformat()
            }
            
            # Save to Excel FIRST (before posting to Discord)
            excel_success = await self._save_new_submission(data)
            if not excel_success:
                print(f"⚠️ [DIRECT WARNING] Failed to save submission for {wallet} to Excel")
                # Continue anyway, maybe Excel is locked or has permissions issue
            
            # Store in memory with lock
            async with self._lock:
                self.pending_submissions[wallet] = submission
            
            # Create and send embed
            embed = self._create_submission_embed(submission)
            view = self._create_submission_review_buttons(wallet)
            
            try:
                print(f"[DIRECT] Sending message to channel #{channel.name}...")
                message = await channel.send(embed=embed, view=view)
                submission['message_id'] = message.id
                
                # Update stored submission with message_id
                async with self._lock:
                    if wallet in self.pending_submissions:
                        self.pending_submissions[wallet]['message_id'] = message.id
                
                print(f"✅ [DIRECT SUCCESS] Posted submission for {wallet}, message ID: {message.id}")
                print(f"   Name: {data.get('name')}")
                print(f"   Role: {data.get('role')}")
                print(f"   Wallet: {wallet}")
                print(f"   Channel: #{channel.name}")
                print(f"   Message URL: {message.jump_url}")
                
                return message
                
            except discord.HTTPException as e:
                print(f"[DIRECT ERROR] Discord API error: {e}")
                print(f"[DIRECT ERROR] Status: {e.status}")
                print(f"[DIRECT ERROR] Code: {e.code}")
                print(f"[DIRECT ERROR] Text: {e.text}")
                
                # Clean up from pending submissions on failure
                async with self._lock:
                    self.pending_submissions.pop(wallet, None)
                return None
                
        except KeyError as e:
            print(f"[DIRECT ERROR] Missing key in data: {e}")
            return None
        except Exception as e:
            print(f"[DIRECT ERROR] Unexpected error: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    def _create_submission_embed(self, data: dict) -> discord.Embed:
        """Create a Discord embed for a submission"""
        submission_data = data.get('data', {})
        status = data.get('status', 'Pending')
        
        color_map = {
            "Approved": discord.Color.green(),
            "Rejected": discord.Color.red(),
            "Pending": discord.Color.gold(),
            "Changes Requested": discord.Color.orange(),
            "On Hold": discord.Color.light_grey()
        }
        color = color_map.get(status, discord.Color.gold())
        
        embed = discord.Embed(
            title=f"🎯 New Talent Submission - {status}",
            description=f"**{submission_data.get('name', 'N/A')}** applying for **{submission_data.get('role', 'N/A')}**",
            color=color,
            timestamp=datetime.now()
        )
        
        # Add thumbnail if available
        if submission_data.get('profilePicture'):
            embed.set_thumbnail(url=submission_data['profilePicture'])
        
        # Basic Information
        basic_info = [
            f"**Injective Role:** {submission_data.get('injectiveRole', 'N/A')}",
            f"**Experience:** {submission_data.get('experience', 'N/A')}",
            f"**Education:** {submission_data.get('education', 'N/A')}",
            f"**Location:** {submission_data.get('location', 'N/A')}",
            f"**Availability:** {'✅ Yes' if submission_data.get('available') else '❌ No'}",
            f"**Monthly Rate:** {submission_data.get('monthlyRate', 'N/A')}"
        ]
        embed.add_field(name="📋 Basic Information", value="\n".join(basic_info), inline=False)
        
        # Wallet Information
        wallet = data.get('wallet', 'N/A')
        embed.add_field(
            name="💰 Wallet", 
            value=f"`{wallet}`\n**Type:** {submission_data.get('walletType', 'N/A')}",
            inline=False
        )
        
        # Blockchain Info
        blockchain_info = [
            f"**NFT Holdings:** {submission_data.get('nftHold', 'N/A')}",
            f"**Token Holdings:** {submission_data.get('tokenHold', 'N/A')}"
        ]
        embed.add_field(name="🔗 Blockchain Info", value="\n".join(blockchain_info), inline=False)
        
        # Skills & Languages
        skills = "• " + "\n• ".join(submission_data.get('skills', [])) if submission_data.get('skills') else "None specified"
        languages = "• " + "\n• ".join(submission_data.get('languages', [])) if submission_data.get('languages') else "None specified"
        embed.add_field(name="🛠️ Skills", value=skills[:500] + "..." if len(skills) > 500 else skills, inline=True)
        embed.add_field(name="🗣️ Languages", value=languages[:500] + "..." if len(languages) > 500 else languages, inline=True)
        
        # Contact Information
        contact_info = [
            f"**Discord:** {submission_data.get('discord', '-')}",
            f"**Email:** {submission_data.get('email', '-')}",
            f"**Phone:** {submission_data.get('phone', '-')}",
            f"**Telegram:** {submission_data.get('telegram', '-')}",
            f"**X/Twitter:** {submission_data.get('X', '-')}",
            f"**GitHub:** {submission_data.get('github', '-')}"
        ]
        embed.add_field(name="📞 Contact Info", value="\n".join(contact_info), inline=False)
        
        # Links
        links = []
        if submission_data.get('portfolio'):
            links.append(f"**Portfolio:** [Link]({submission_data['portfolio']})")
        if submission_data.get('cv'):
            links.append(f"**CV/Resume:** [Download]({submission_data['cv']})")
        if links:
            embed.add_field(name="🔗 Links", value="\n".join(links), inline=False)
        
        # Bio
        bio = submission_data.get('bio', 'No bio provided')
        embed.add_field(
            name="📝 Bio", 
            value=f"{bio[:500]}{'...' if len(bio) > 500 else ''}", 
            inline=False
        )
        
        # Footer with wallet for identification
        embed.set_footer(text=f"Wallet: {wallet[:8]}...{wallet[-6:]} • Click buttons below to approve/reject")
        
        return embed
    
    def _create_submission_review_buttons(self, wallet: str) -> View:
        """Create buttons for approving/rejecting submissions"""
        view = View(timeout=None)  
        
        approve_button = Button(
            label="Approve", 
            style=discord.ButtonStyle.success, 
            custom_id=f"submission:approve:{wallet}",
            emoji="✅"
        )
        
        reject_button = Button(
            label="Reject", 
            style=discord.ButtonStyle.danger, 
            custom_id=f"submission:reject:{wallet}",
            emoji="❌"
        )
        
        view.add_item(approve_button)
        view.add_item(reject_button)
        
        return view
    
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions"""
        if interaction.type != discord.InteractionType.component:
            return
            
        try:
            custom_id = interaction.data.get('custom_id', '')
            print(f"[INTERACTION] Received interaction with custom_id: {custom_id}")
            
            if ':' not in custom_id:
                return
                
            # Parse the custom_id
            parts = custom_id.split(':', 2)
            if len(parts) == 3:
                action_type, action, wallet = parts
            else:
                return

            if action_type == "submission":
                await self._handle_submission_interaction(interaction, action, wallet)
                
        except Exception as e:
            print(f"[INTERACTION ERROR] Error handling interaction: {e}")
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An error occurred while processing your request!",
                        ephemeral=True
                    )
            except:
                pass
    
    async def _handle_submission_interaction(self, interaction: discord.Interaction, action: str, wallet: str):
        """Handle submission button interactions (approve/reject)"""
        print(f"[INTERACTION] Handling {action} for wallet: {wallet}")
        
        # Get the submission
        submission = self.pending_submissions.get(wallet)
        
        if not submission:
            print(f"[INTERACTION] No pending submission found for wallet: {wallet}")
            await interaction.response.send_message(
                "❌ Submission not found or already processed!",
                ephemeral=True
            )
            return
        
        # Update status based on action
        if action == "approve":
            submission['status'] = "Approved"
            success = await self._update_excel_status(wallet, "Approved")
            
            if success:
                await interaction.response.send_message(
                    f"✅ Submission approved and Excel updated for wallet `{wallet}`!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"✅ Approved but failed to update Excel for wallet `{wallet}`!",
                    ephemeral=True
                )
                
        elif action == "reject":
            submission['status'] = "Rejected"
            success = await self._update_excel_status(wallet, "Rejected")
            
            if success:
                await interaction.response.send_message(
                    f"❌ Submission rejected and Excel updated for wallet `{wallet}`!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Rejected but failed to update Excel for wallet `{wallet}`!",
                    ephemeral=True
                )
                
        elif action == "changes":
            # For now, just mark as changes requested
            submission['status'] = "Changes Requested"
            success = await self._update_excel_status(wallet, "Changes Requested")
            
            if success:
                await interaction.response.send_message(
                    f"✏️ Changes requested for wallet `{wallet}`. Status updated in Excel.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"✏️ Changes requested but failed to update Excel for wallet `{wallet}`!",
                    ephemeral=True
                )
        
        # Update the message embed to show new status
        await self._update_submission_message(interaction, submission)
        
        # Remove from pending submissions after processing
        async with self._lock:
            if wallet in self.pending_submissions:
                del self.pending_submissions[wallet]
                print(f"[INTERACTION] Removed wallet {wallet} from pending submissions")
    
    async def _update_excel_status(self, wallet_address: str, new_status: str) -> bool:
        """Update the status column in Excel for a specific wallet"""
        try:
            wb = load_workbook(self.excel_file)
            ws = wb.active
            
            row = await self._find_submission_row(wallet_address)
            if not row:
                print(f"[EXCEL] No row found for wallet: {wallet_address}")
                wb.close()
                return False
            
            print(f"[EXCEL] Updating status for wallet {wallet_address} at row {row} to: {new_status}")
            ws[f'Z{row}'] = new_status
            wb.save(self.excel_file)
            wb.close()
            
            print(f"[EXCEL] Successfully updated status for {wallet_address} to {new_status}")
            return True
            
        except Exception as e:
            print(f"[EXCEL ERROR] Error updating Excel status: {e}")
            traceback.print_exc()
            return False
    
    async def _update_submission_message(self, interaction: discord.Interaction, submission: dict):
        """Update the Discord message embed with new status"""
        try:
            # Get the original message
            message = await interaction.channel.fetch_message(submission['message_id'])
            
            # Create updated embed
            embed = self._create_submission_embed(submission)
            
            # Update the message (remove buttons since it's processed)
            await message.edit(embed=embed, view=None)
            print(f"[MESSAGE] Updated message {message.id} with status: {submission['status']}")
            
        except Exception as e:
            print(f"[MESSAGE ERROR] Error updating submission message: {e}")
    
    def submit_from_thread(self, data: dict) -> bool:
        """
        Thread-safe method to submit data from any thread.
        Returns True if submission was added to queue, False otherwise.
        """
        try:
            print(f"[THREAD] Adding submission to queue for: {data.get('walletAddress', 'Unknown')}")
            self._thread_submission_queue.put(data)
            return True
        except Exception as e:
            print(f"[THREAD ERROR] Failed to add submission to queue: {e}")
            traceback.print_exc()
            return False
    
    async def post_submission(self, data: dict) -> Optional[discord.Message]:
        """
        Async method for posting submissions.
        Can be called from within the bot's event loop.
        """
        return await self._process_submission_directly(data)
    
    def start(self):
        """Start the bot"""
        if not self.bot_code:
            print("❌ Cannot start bot: No token provided!")
            return
            
        print("🤖 Starting Talent Hub Bot...")
        print("=" * 50)
        print("IMPORTANT: Make sure:")
        print("1. Your bot token is correct in the .env file")
        print("2. The bot is invited to your server with proper permissions")
        print("3. The channel ID (1374018261578027129) is correct")
        print("4. The bot has 'Send Messages' and 'Embed Links' permissions")
        print("=" * 50)
        
        try:
            self.bot.run(self.bot_code)
        except discord.LoginFailure:
            print("❌ Failed to login. Check your bot token!")
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            traceback.print_exc()


# Create global instance
talent_hub_bot = TalentHubBot()


def submit_to_discord(data: dict) -> bool:
    """
    Use this function from any thread to submit data to Discord.
    Returns True if submission was queued successfully, False otherwise.
    """
    try:
        # Validate required fields
        required_fields = ['walletAddress', 'name', 'role']
        for field in required_fields:
            if field not in data:
                print(f"[SUBMIT ERROR] Missing required field: {field}")
                return False
        
        print(f"[SUBMIT] Submitting data for: {data.get('name')} ({data.get('walletAddress')})")
        
        # Use the thread-safe method
        success = talent_hub_bot.submit_from_thread(data)
        
        if success:
            print(f"✅ [SUBMIT SUCCESS] Submission queued for: {data.get('walletAddress')}")
            print(f"   Name: {data.get('name')}")
            print(f"   Role: {data.get('role')}")
            print(f"   Will appear in Discord channel #talent-submissions (ID: 1374018261578027129)")
        else:
            print(f"❌ [SUBMIT ERROR] Failed to queue submission for: {data.get('walletAddress')}")
        
        return success
        
    except Exception as e:
        print(f"❌ [SUBMIT ERROR] Exception in submit_to_discord: {e}")
        traceback.print_exc()
        return False


# Test function
def test_submission():
    """Test submission with sample data"""
    test_data = {
        'name': 'Pedro Test',
        'role': 'Community Manager',
        'skills': ['Social Media'],
        'experience': '<1 year',
        'education': "Bachelor's Degree",
        'location': 'Canada',
        'bio': 'Test bio for Pedro',
        'telegram': 'https://t.me/WEPEtoken',
        'x': 'InjPedro',
        'github': '-',
        'email': 'pedroinjective@gmail.com',
        'phone': '',
        'portfolio': 'https://pedroinjraccoon.online/',
        'cv': 'https://docs.google.com/',
        'profilePicture': 'https://i.postimg.cc/xTdtvd0P/Ontwerp-zonder-titel-2025-05-06-T221929-981.png',
        'injectiveRole': 'Injective Supporter',
        'languages': ['Swedish'],
        'available': True,
        'monthlyRate': '$500-$1,000',
        'discord': 'pedro_test',
        'walletAddress': 'inj1x6u08aa3plhk3utjk7wpyjkurtwnwp6dhudhj',
        'walletType': 'keplr',
        'nftHold': '1',
        'tokenHold': '1697971'
    }
    
    print("🧪 Testing submission...")
    success = submit_to_discord(test_data)
    if success:
        print("✅ Test submission queued successfully!")
    else:
        print("❌ Test submission failed!")


# For direct async calls (from within the bot's event loop)
async def post_submission_async(data: dict):
    """Use this if calling from within the bot's event loop"""
    return await talent_hub_bot.post_submission(data)


if __name__ == "__main__":
    print("🚀 Starting Talent Hub Bot...")
    
    # Uncomment to test immediately
    #test_submission()
    
    # Start the bo
    talent_hub_bot.start()