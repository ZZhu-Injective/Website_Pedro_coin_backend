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
        self.queued_submissions: Dict[str, dict] = {}   
        self.pending_updates: Dict[str, dict] = {}
        self.excel_file = "Atalent_submissions.xlsx"
        self.bot_code = os.getenv("DISCORD_BOT")
        
        if not self.bot_code:
            print("❌ ERROR: DISCORD_BOT token not found in environment variables!")
            print("💡 Make sure you have a .env file with: DISCORD_BOT=your_bot_token_here")
            return
        
        self._lock = asyncio.Lock()
        
        self._thread_submission_queue = thread_queue.Queue()
        self._queue_processing = False
        
        self._ensure_excel_file()
        
        self.bot.event(self.on_ready)
        self.bot.event(self.on_interaction)
        
        self.bot.tree.command(name="job_open")(self.job_open_command)
        self.bot.tree.command(name="job_show")(self.show_command)
        self.bot.tree.command(name="job_change")(self.change_command)
        self.bot.tree.command(name="job_remove")(self.remove_command)
        self.bot.tree.command(name="job_variable")(self.column_names_command)
        self.bot.tree.command(name="job_status")(self.job_status_command)
        
        @self.bot.command(name="job_open")
        async def job_open_prefix(ctx):
            await self.job_open_prefix_command(ctx)
            
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
            
        @self.bot.command(name="job_status")
        async def job_status_prefix(ctx):
            await self.job_status_prefix_command(ctx)
    
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
        try:
            wb = load_workbook(self.excel_file, read_only=True)
            ws = wb.active
            
            for row in range(2, ws.max_row + 1):
                cell_value = ws[f'Q{row}'].value
                if cell_value and str(cell_value).strip().lower() == wallet_address.strip().lower():
                    wb.close()
                    return row
            
            wb.close()
            return None
            
        except Exception as e:
            print(f"❌ Error searching Excel file: {e}")
            return None
    
    async def _get_all_records(self) -> List[Tuple[str, str]]:
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
    
    async def job_open_command(self, interaction: discord.Interaction):
        """Open queued submissions for review"""
        await interaction.response.defer()
        
        try:
            # Get queued submissions that haven't been posted to Discord yet
            queued_count = len(self.queued_submissions)
            pending_count = len(self.pending_submissions)
            
            if queued_count == 0:
                embed = discord.Embed(
                    title="📭 Submission Inbox",
                    description="No submissions waiting for review.",
                    color=discord.Color.green()
                )
                embed.add_field(name="📥 Queued", value="0 submissions", inline=True)
                embed.add_field(name="⏳ Pending Review", value=f"{pending_count} submissions", inline=True)
                embed.set_footer(text="Submissions appear here after being submitted via web form")
                
                await interaction.followup.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="📬 Submission Inbox",
                description=f"Showing {queued_count} queued submission(s) for review.",
                color=discord.Color.blue()
            )
            embed.add_field(name="📥 Queued", value=f"{queued_count} submission(s)", inline=True)
            embed.add_field(name="⏳ Pending Review", value=f"{pending_count} submission(s)", inline=True)
            embed.set_footer(text="Use buttons below to review each submission")
            
            view = View(timeout=180)
            
            for wallet, data in list(self.queued_submissions.items())[:5]:  # Show max 5 at once
                btn_label = f"Review: {data.get('data', {}).get('name', 'Unknown')}"
                button = Button(
                    label=btn_label[:80],
                    style=discord.ButtonStyle.primary,
                    custom_id=f"open:review:{wallet}"
                )
                view.add_item(button)
            
            # Add close button
            close_button = Button(
                label="Close Inbox",
                style=discord.ButtonStyle.secondary,
                custom_id="open:close"
            )
            view.add_item(close_button)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ Error in job_open command: {e}")
            traceback.print_exc()
            await interaction.followup.send(
                "An error occurred while opening the submission inbox.",
                ephemeral=True
            )
    
    async def job_open_prefix_command(self, ctx: commands.Context):
        """Open queued submissions for review (prefix command)"""
        try:
            queued_count = len(self.queued_submissions)
            pending_count = len(self.pending_submissions)
            
            if queued_count == 0:
                embed = discord.Embed(
                    title="📭 Submission Inbox",
                    description="No submissions waiting for review.",
                    color=discord.Color.green()
                )
                embed.add_field(name="📥 Queued", value="0 submissions", inline=True)
                embed.add_field(name="⏳ Pending Review", value=f"{pending_count} submissions", inline=True)
                embed.set_footer(text="Submissions appear here after being submitted via web form")
                
                await ctx.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="📬 Submission Inbox",
                description=f"Showing {queued_count} queued submission(s) for review.",
                color=discord.Color.blue()
            )
            embed.add_field(name="📥 Queued", value=f"{queued_count} submission(s)", inline=True)
            embed.add_field(name="⏳ Pending Review", value=f"{pending_count} submission(s)", inline=True)
            embed.set_footer(text="Use buttons below to review each submission")
            
            view = View(timeout=180)
            
            for wallet, data in list(self.queued_submissions.items())[:5]:
                btn_label = f"Review: {data.get('data', {}).get('name', 'Unknown')}"
                button = Button(
                    label=btn_label[:80],
                    style=discord.ButtonStyle.primary,
                    custom_id=f"open:review:{wallet}"
                )
                view.add_item(button)
            
            close_button = Button(
                label="Close Inbox",
                style=discord.ButtonStyle.secondary,
                custom_id="open:close"
            )
            view.add_item(close_button)
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ Error in job_open prefix command: {e}")
            await ctx.send("An error occurred while opening the submission inbox.")
    
    async def job_status_command(self, interaction: discord.Interaction):
        """Show current submission status"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            queued_count = len(self.queued_submissions)
            pending_count = len(self.pending_submissions)
            
            embed = discord.Embed(
                title="📊 Submission Status",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📥 Queued Submissions",
                value=f"**{queued_count}** submission(s) waiting in inbox",
                inline=False
            )
            
            embed.add_field(
                name="⏳ Pending Review",
                value=f"**{pending_count}** submission(s) posted for review",
                inline=False
            )
            
            if queued_count > 0:
                recent_submissions = []
                for wallet, data in list(self.queued_submissions.items())[:3]:
                    name = data.get('data', {}).get('name', 'Unknown')
                    role = data.get('data', {}).get('role', 'Unknown')
                    recent_submissions.append(f"• **{name}** - {role}")
                
                if recent_submissions:
                    embed.add_field(
                        name="📋 Recent Submissions",
                        value="\n".join(recent_submissions),
                        inline=False
                    )
            
            embed.set_footer(text="Use /job_open to review queued submissions")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Error in job_status command: {e}")
            await interaction.followup.send(
                "An error occurred while fetching status.",
                ephemeral=True
            )
    
    async def job_status_prefix_command(self, ctx: commands.Context):
        """Show current submission status (prefix command)"""
        try:
            queued_count = len(self.queued_submissions)
            pending_count = len(self.pending_submissions)
            
            embed = discord.Embed(
                title="📊 Submission Status",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📥 Queued Submissions",
                value=f"**{queued_count}** submission(s) waiting in inbox",
                inline=False
            )
            
            embed.add_field(
                name="⏳ Pending Review",
                value=f"**{pending_count}** submission(s) posted for review",
                inline=False
            )
            
            if queued_count > 0:
                recent_submissions = []
                for wallet, data in list(self.queued_submissions.items())[:3]:
                    name = data.get('data', {}).get('name', 'Unknown')
                    role = data.get('data', {}).get('role', 'Unknown')
                    recent_submissions.append(f"• **{name}** - {role}")
                
                if recent_submissions:
                    embed.add_field(
                        name="📋 Recent Submissions",
                        value="\n".join(recent_submissions),
                        inline=False
                    )
            
            embed.set_footer(text="Use !job_open to review queued submissions")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Error in job_status prefix command: {e}")
            await ctx.send("An error occurred while fetching status.")
    
    async def column_names_command(self, interaction: discord.Interaction):
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
                
                success = await self.bot_instance._delete_record(self.wallet)
                
                if success:
                    embed = discord.Embed(
                        title="Record Deleted Successfully",
                        description=f"Record for wallet `{self.wallet}` has been deleted.",
                        color=discord.Color.red()
                    )
                    
                    await interaction.edit_original_response(embed=embed, view=None)
                    
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
        row = await self._find_submission_row(wallet_address)
        if not row:
            await ctx.send(f"No record found for wallet address: `{wallet_address}`")
            return
        
        record = await self._get_record_details(wallet_address)
        if not record:
            await ctx.send("Could not retrieve record details.")
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
                
                success = await self.bot_instance._delete_record(self.wallet)
                
                if success:
                    embed = discord.Embed(
                        title="Record Deleted Successfully",
                        description=f"Record for wallet `{self.wallet}` has been deleted.",
                        color=discord.Color.red()
                    )
                    
                    await interaction.message.edit(embed=embed, view=None)
                    await interaction.response.send_message("Record deleted!", ephemeral=True)
                    
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
            
            print(f"[EXCEL SAVE] Saving submission for wallet: {wallet}")
            
            existing_row = await self._find_submission_row(wallet)
            if existing_row:
                print(f"⚠️ [EXCEL SAVE] Wallet {wallet} already exists in row {existing_row}. Updating instead.")
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
                "Queued"  # Changed from "Pending"
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
            ws[f'Z{row}'] = "Queued"  # Changed from "Pending"
            
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
            synced = await self.bot.tree.sync()
            print(f"✅ Synced {len(synced)} command(s)")
            
            asyncio.create_task(self._process_submission_queue())
            print("✅ Started submission queue processor")
            
            # Send a notification that bot is ready and has queued submissions
            if self.queued_submissions:
                notification = f"📬 Talent Hub Bot is ready! There are **{len(self.queued_submissions)}** submission(s) waiting for review. Use `/job_open` to review them."
                if channel:
                    await channel.send(notification)
            
        except Exception as e:
            print(f"❌ Error syncing commands: {e}")
            traceback.print_exc()
    
    async def _process_submission_queue(self):
        """Process submissions from the thread-safe queue - MODIFIED: Only add to queued_submissions"""
        print("🔄 Submission queue processor started")
        while True:
            try:
                if not self._thread_submission_queue.empty():
                    pending = []
                    while not self._thread_submission_queue.empty():
                        try:
                            submission = self._thread_submission_queue.get_nowait()
                            pending.append(submission)
                            print(f"[QUEUE] Got submission from queue for: {submission.get('walletAddress', 'Unknown')}")
                        except thread_queue.Empty:
                            break
                    
                    for data in pending:
                        try:
                            print(f"[QUEUE] Adding submission to queued list: {data.get('walletAddress', 'Unknown')}")
                            await self._add_to_queued_submissions(data)
                        except Exception as e:
                            print(f"[QUEUE ERROR] Error processing submission: {e}")
                            traceback.print_exc()
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"[QUEUE ERROR] Error in queue processor: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)
    
    async def _add_to_queued_submissions(self, data: dict):
        """Add a submission to the queued list (not post to Discord yet)"""
        try:
            wallet = data.get('walletAddress', '').strip()
            
            if not wallet:
                print(f"[QUEUE ERROR] No wallet address in data")
                return
            
            async with self._lock:
                if wallet in self.queued_submissions or wallet in self.pending_submissions:
                    print(f"[QUEUE WARNING] Duplicate submission for {wallet}")
                    return
            
            # Save to Excel first
            excel_success = await self._save_new_submission(data)
            if not excel_success:
                print(f"⚠️ [QUEUE WARNING] Failed to save submission for {wallet} to Excel")
            
            submission = {
                'data': data,
                'status': "Queued",
                'wallet': wallet,
                'timestamp': datetime.now().isoformat()
            }
            
            async with self._lock:
                self.queued_submissions[wallet] = submission
            
            print(f"✅ [QUEUE SUCCESS] Added submission to queued list for: {wallet}")
            print(f"   Name: {data.get('name')}")
            print(f"   Role: {data.get('role')}")
            print(f"   Queued submissions count: {len(self.queued_submissions)}")
            
            # Send notification to Discord channel
            channel = self.bot.get_channel(self.submission_channel_id)
            if channel:
                notification_embed = discord.Embed(
                    title="📥 New Submission Received",
                    description=f"**{data.get('name', 'Unknown')}** has submitted their talent profile.",
                    color=discord.Color.green()
                )
                notification_embed.add_field(name="Role", value=data.get('role', 'N/A'), inline=True)
                notification_embed.add_field(name="Status", value="Queued for review", inline=True)
                notification_embed.add_field(name="Queue Position", value=f"{len(self.queued_submissions)} in queue", inline=True)
                notification_embed.set_footer(text=f"Use /job_open to review | Total queued: {len(self.queued_submissions)}")
                
                await channel.send(embed=notification_embed)
            
        except Exception as e:
            print(f"[QUEUE ERROR] Error adding to queued submissions: {e}")
            traceback.print_exc()
    
    async def _post_submission_to_channel(self, wallet: str) -> Optional[discord.Message]:
        """Post a specific queued submission to the channel for review"""
        try:
            if wallet not in self.queued_submissions:
                print(f"[POST ERROR] Wallet {wallet} not in queued submissions")
                return None
            
            submission = self.queued_submissions[wallet]
            data = submission.get('data', {})
            
            channel = self.bot.get_channel(self.submission_channel_id)
            if not channel:
                print(f"[POST ERROR] Submission channel {self.submission_channel_id} not found!")
                return None
                
            bot_member = channel.guild.me
            permissions = channel.permissions_for(bot_member)
            
            if not permissions.send_messages:
                print("[POST ERROR] Bot doesn't have permission to send messages in this channel!")
                return None
            
            if not permissions.embed_links:
                print("[POST ERROR] Bot doesn't have permission to embed links in this channel!")
                return None
            
            # Update status to Pending
            submission['status'] = "Pending"
            
            embed = self._create_submission_embed(submission)
            view = self._create_submission_review_buttons(wallet)
            
            print(f"[POST] Sending submission to channel #{channel.name} for review...")
            message = await channel.send(embed=embed, view=view)
            submission['message_id'] = message.id
            
            # Move from queued to pending
            async with self._lock:
                self.pending_submissions[wallet] = submission
                del self.queued_submissions[wallet]
            
            # Update Excel status from "Queued" to "Pending"
            await self._update_excel_status(wallet, "Pending")
            
            print(f"✅ [POST SUCCESS] Posted submission for {wallet}, message ID: {message.id}")
            print(f"   Name: {data.get('name')}")
            print(f"   Role: {data.get('role')}")
            print(f"   Queued left: {len(self.queued_submissions)}")
            print(f"   Pending now: {len(self.pending_submissions)}")
            
            return message
                
        except KeyError as e:
            print(f"[POST ERROR] Missing key in data: {e}")
            return None
        except Exception as e:
            print(f"[POST ERROR] Unexpected error: {type(e).__name__}: {e}")
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
            "Queued": discord.Color.blue(),
            "Changes Requested": discord.Color.orange(),
            "On Hold": discord.Color.light_grey()
        }
        color = color_map.get(status, discord.Color.gold())
        
        embed = discord.Embed(
            title=f"🎯 Talent Submission - {status}",
            description=f"**{submission_data.get('name', 'N/A')}** applying for **{submission_data.get('role', 'N/A')}**",
            color=color,
            timestamp=datetime.now()
        )
        
        if submission_data.get('profilePicture'):
            embed.set_thumbnail(url=submission_data['profilePicture'])
        
        basic_info = [
            f"**Injective Role:** {submission_data.get('injectiveRole', 'N/A')}",
            f"**Experience:** {submission_data.get('experience', 'N/A')}",
            f"**Education:** {submission_data.get('education', 'N/A')}",
            f"**Location:** {submission_data.get('location', 'N/A')}",
            f"**Availability:** {'✅ Yes' if submission_data.get('available') else '❌ No'}",
            f"**Monthly Rate:** {submission_data.get('monthlyRate', 'N/A')}"
        ]
        embed.add_field(name="📋 Basic Information", value="\n".join(basic_info), inline=False)
        
        wallet = data.get('wallet', 'N/A')
        embed.add_field(
            name="💰 Wallet", 
            value=f"`{wallet}`\n**Type:** {submission_data.get('walletType', 'N/A')}",
            inline=False
        )
        
        blockchain_info = [
            f"**NFT Holdings:** {submission_data.get('nftHold', 'N/A')}",
            f"**Token Holdings:** {submission_data.get('tokenHold', 'N/A')}"
        ]
        embed.add_field(name="🔗 Blockchain Info", value="\n".join(blockchain_info), inline=False)
        
        skills = "• " + "\n• ".join(submission_data.get('skills', [])) if submission_data.get('skills') else "None specified"
        languages = "• " + "\n• ".join(submission_data.get('languages', [])) if submission_data.get('languages') else "None specified"
        embed.add_field(name="🛠️ Skills", value=skills[:500] + "..." if len(skills) > 500 else skills, inline=True)
        embed.add_field(name="🗣️ Languages", value=languages[:500] + "..." if len(languages) > 500 else languages, inline=True)
        
        contact_info = [
            f"**Discord:** {submission_data.get('discord', '-')}",
            f"**Email:** {submission_data.get('email', '-')}",
            f"**Phone:** {submission_data.get('phone', '-')}",
            f"**Telegram:** {submission_data.get('telegram', '-')}",
            f"**X/Twitter:** {submission_data.get('X', '-')}",
            f"**GitHub:** {submission_data.get('github', '-')}"
        ]
        embed.add_field(name="📞 Contact Info", value="\n".join(contact_info), inline=False)
        
        links = []
        if submission_data.get('portfolio'):
            links.append(f"**Portfolio:** [Link]({submission_data['portfolio']})")
        if submission_data.get('cv'):
            links.append(f"**CV/Resume:** [Download]({submission_data['cv']})")
        if links:
            embed.add_field(name="🔗 Links", value="\n".join(links), inline=False)
        
        bio = submission_data.get('bio', 'No bio provided')
        embed.add_field(
            name="📝 Bio", 
            value=f"{bio[:500]}{'...' if len(bio) > 500 else ''}", 
            inline=False
        )
        
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
        
        close_button = Button(
            label="Close", 
            style=discord.ButtonStyle.secondary, 
            custom_id=f"submission:close:{wallet}",
            emoji="🔒"
        )
        
        view.add_item(approve_button)
        view.add_item(reject_button)
        view.add_item(close_button)
        
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
                
            parts = custom_id.split(':', 2)
            
            if len(parts) == 3:
                action_type, action, wallet = parts
                
                # Respond immediately to avoid timeout
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                
                print(f"[INTERACTION] Parsed - Type: {action_type}, Action: {action}, Wallet: {wallet}")
                
                if action_type == "submission":
                    asyncio.create_task(self._handle_submission_interaction(interaction, action, wallet))
                elif action_type == "open":
                    asyncio.create_task(self._handle_open_interaction(interaction, action, wallet))
                else:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"❌ Unknown action type: {action_type}",
                            ephemeral=True
                        )
            else:
                print(f"[INTERACTION] Invalid parts count: {len(parts)}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Invalid interaction format!",
                        ephemeral=True
                    )
                
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
    
    async def _handle_open_interaction(self, interaction: discord.Interaction, action: str, wallet: str):
        """Handle job_open button interactions"""
        print(f"[OPEN INTERACTION] Processing {action} for wallet: {wallet}")
        
        try:
            if action == "review":
                # Post this specific submission to channel
                message = await self._post_submission_to_channel(wallet)
                
                if message:
                    await interaction.followup.send(
                        f"✅ Submission for wallet `{wallet}` has been posted for review!",
                        ephemeral=True
                    )
                    
                    # Update the original job_open message
                    try:
                        original_embed = interaction.message.embeds[0]
                        updated_embed = discord.Embed(
                            title="📭 Submission Inbox",
                            description=f"Submission for `{wallet}` has been moved to review channel.",
                            color=discord.Color.green()
                        )
                        updated_embed.add_field(name="📥 Queued", value=f"{len(self.queued_submissions)} submission(s)", inline=True)
                        updated_embed.add_field(name="⏳ Pending Review", value=f"{len(self.pending_submissions)} submission(s)", inline=True)
                        updated_embed.set_footer(text="Use /job_open again to review more submissions")
                        
                        await interaction.message.edit(embed=updated_embed, view=None)
                    except:
                        pass
                else:
                    await interaction.followup.send(
                        f"❌ Failed to post submission for wallet `{wallet}`",
                        ephemeral=True
                    )
                    
            elif action == "close":
                await interaction.message.edit(content="Inbox closed.", embed=None, view=None)
                await interaction.followup.send("✅ Inbox closed.", ephemeral=True)
                
        except Exception as e:
            print(f"[OPEN INTERACTION ERROR] Error: {e}")
            traceback.print_exc()
            await interaction.followup.send(
                "❌ An error occurred while processing your request!",
                ephemeral=True
            )
    
    async def _handle_submission_interaction(self, interaction: discord.Interaction, action: str, wallet: str):
        """Handle submission button interactions"""
        print(f"[SUBMISSION INTERACTION] Processing {action} for wallet: {wallet}")
        
        try:
            # Find the submission
            submission = None
            submission_key = None
            
            for key, pending_data in list(self.pending_submissions.items()):
                if (key == wallet or 
                    key.lower() == wallet.lower() or
                    pending_data.get('data', {}).get('walletAddress', '').strip() == wallet or
                    pending_data.get('data', {}).get('walletAddress', '').strip().lower() == wallet.lower() or
                    pending_data.get('message_id') == interaction.message.id):
                    
                    submission = pending_data
                    submission_key = key
                    print(f"[INTERACTION] Found submission with key: {key}")
                    break
            
            if not submission:
                print(f"[INTERACTION] No submission found for wallet: {wallet}")
                await interaction.followup.send(
                    f"❌ Submission not found or already processed! (Looking for: `{wallet}`)",
                    ephemeral=True
                )
                return
            
            # Process the action
            if action == "approve":
                submission['status'] = "Approved"
                success = await self._update_excel_status(submission_key, "Approved")
                
                if success:
                    await interaction.followup.send(
                        f"✅ Submission approved and database updated for wallet `{submission_key}`!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"✅ Approved but failed to update database for wallet `{submission_key}`!",
                        ephemeral=True
                    )
                    
            elif action == "reject":
                submission['status'] = "Rejected"
                success = await self._update_excel_status(submission_key, "Rejected")
                
                if success:
                    await interaction.followup.send(
                        f"❌ Submission rejected and Excel database for wallet `{submission_key}`!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Rejected but failed to update database for wallet `{submission_key}`!",
                        ephemeral=True
                    )
                    
            elif action == "close":
                submission['status'] = "Closed"
                success = await self._update_excel_status(submission_key, "Closed")
                
                if success:
                    await interaction.followup.send(
                        f"🔒 Submission closed for wallet `{submission_key}`!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"🔒 Closed but failed to update database for wallet `{submission_key}`!",
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    f"❌ Unknown action: {action}",
                    ephemeral=True
                )
                return
            
            # Update the Discord message - remove buttons
            try:
                embed = self._create_submission_embed(submission)
                await interaction.message.edit(embed=embed, view=None)
                print(f"[INTERACTION] Updated message with new status: {submission['status']}")
            except Exception as e:
                print(f"[INTERACTION] Error updating message: {e}")
            
            # Remove from pending submissions
            if submission_key in self.pending_submissions:
                del self.pending_submissions[submission_key]
                print(f"[INTERACTION] Removed {submission_key} from pending submissions")
                
        except Exception as e:
            print(f"[INTERACTION BACKGROUND ERROR] Error in background processing: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    "❌ An error occurred while processing your request!",
                    ephemeral=True
                )
            except:
                pass
    
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
    
    def submit_from_thread(self, data: dict) -> bool:
        """
        Thread-safe method to submit data from any thread.
        Returns True if submission was added to queue, False otherwise.
        """
        try:
            print(f"[THREAD] Adding submission to queue for: {data.get('walletAddress', 'Unknown')}")
            self._thread_submission_queue.put(data)
            
            # Log the submission details
            print(f"[THREAD] Submission details:")
            print(f"  - Name: {data.get('name')}")
            print(f"  - Role: {data.get('role')}")
            print(f"  - Wallet: {data.get('walletAddress')}")
            print(f"  - Queue size: {self._thread_submission_queue.qsize()}")
            print(f"  - Total queued: {len(self.queued_submissions) + 1}")
            
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
        return await self._post_submission_to_channel(data.get('walletAddress', ''))
    
    def start(self):
        """Start the bot"""
        if not self.bot_code:
            print("❌ Cannot start bot: No token provided!")
            return
            
        print("🤖 Starting Talent Hub Bot...")
        print("=" * 50)
        print("NEW WORKFLOW:")
        print("1. Submissions go to queued list")
        print("2. Use /job_open to review queued submissions")
        print("3. Click 'Review' button to post submission to channel")
        print("4. Use approve/reject/close buttons on posted submissions")
        print("=" * 50)
        
        try:
            self.bot.run(self.bot_code)
        except discord.LoginFailure:
            print("❌ Failed to login. Check your bot token!")
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            traceback.print_exc()


talent_hub_bot = TalentHubBot()


def submit_to_discord(data: dict) -> bool:
    """
    Use this function from any thread to submit data to Discord.
    Returns True if submission was queued successfully, False otherwise.
    """
    try:
        required_fields = ['walletAddress', 'name', 'role']
        for field in required_fields:
            if field not in data:
                print(f"[SUBMIT ERROR] Missing required field: {field}")
                return False
        
        print(f"[SUBMIT] Submitting data for: {data.get('name')} ({data.get('walletAddress')})")
        
        success = talent_hub_bot.submit_from_thread(data)
        
        if success:
            print(f"✅ [SUBMIT SUCCESS] Submission queued for: {data.get('walletAddress')}")
            print(f"   Name: {data.get('name')}")
            print(f"   Role: {data.get('role')}")
            print(f"   Status: Queued (Use /job_open to review)")
        else:
            print(f"❌ [SUBMIT ERROR] Failed to queue submission for: {data.get('walletAddress')}")
        
        return success
        
    except Exception as e:
        print(f"❌ [SUBMIT ERROR] Exception in submit_to_discord: {e}")
        traceback.print_exc()
        return False


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
        print("💡 Use /job_open in Discord to review this submission")
    else:
        print("❌ Test submission failed!")


async def post_submission_async(data: dict):
    """Use this if calling from within the bot's event loop"""
    return await talent_hub_bot.post_submission(data)


if __name__ == "__main__":
    print("🚀 Starting Talent Hub Bot...")
    
    # Uncomment to test immediately
    #test_submission()
    
    talent_hub_bot.start()