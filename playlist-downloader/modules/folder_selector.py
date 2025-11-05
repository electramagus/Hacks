#!/usr/bin/env python3
"""
Folder Selection Module
========================
User-friendly folder selection for non-technical users.
Supports GUI file dialogs on all platforms and CLI fallback.
"""

import os
import sys
from pathlib import Path
from typing import Optional


def select_folder_gui() -> Optional[str]:
    """
    Open a GUI folder selection dialog.
    Works cross-platform (Windows, macOS, Linux).
    
    Returns:
        Selected folder path or None if cancelled
    """
    try:
        # Try tkinter first (built into Python on most systems)
        import tkinter as tk
        from tkinter import filedialog
        
        # Create root window but hide it
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)  # Bring to front
        
        # Open folder selection dialog
        folder_path = filedialog.askdirectory(
            title="Select Download Folder",
            mustexist=False  # Allow selecting folders that don't exist yet
        )
        
        root.destroy()
        
        if folder_path:
            return folder_path
        return None
        
    except ImportError:
        # tkinter not available, return None to fall back to CLI
        return None
    except Exception as e:
        print(f"Warning: GUI dialog failed: {e}")
        return None


def create_folder_interactive(base_path: str, folder_name: str) -> Optional[str]:
    """
    Create a new folder at the given location interactively.
    
    Args:
        base_path: Parent directory path
        folder_name: Name for the new folder
        
    Returns:
        Full path to created folder or None if failed
    """
    try:
        full_path = os.path.join(base_path, folder_name)
        
        # Check if already exists
        if os.path.exists(full_path):
            print(f"✓ Folder already exists: {full_path}")
            return full_path
        
        # Create the folder
        os.makedirs(full_path, exist_ok=True)
        print(f"✓ Created folder: {full_path}")
        return full_path
        
    except Exception as e:
        print(f"✗ Error creating folder: {e}")
        return None


def select_folder_cli() -> Optional[str]:
    """
    CLI-based folder selection for when GUI is not available.
    Provides options to:
    1. Use default location (./downloads)
    2. Enter custom path
    3. Browse from home directory
    4. Create new folder
    
    Returns:
        Selected folder path or None if cancelled
    """
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich.table import Table
    
    console = Console()
    
    # Get some sensible default locations
    home_dir = str(Path.home())
    current_dir = os.getcwd()
    default_dir = os.path.join(current_dir, 'downloads')
    
    # Common locations for different platforms
    if sys.platform == 'win32':
        music_dir = os.path.join(home_dir, 'Music')
        docs_dir = os.path.join(home_dir, 'Documents')
        common_dirs = [default_dir, music_dir, docs_dir]
    elif sys.platform == 'darwin':  # macOS
        music_dir = os.path.join(home_dir, 'Music')
        docs_dir = os.path.join(home_dir, 'Documents')
        common_dirs = [default_dir, music_dir, docs_dir]
    else:  # Linux
        music_dir = os.path.join(home_dir, 'Music')
        docs_dir = os.path.join(home_dir, 'Documents')
        common_dirs = [default_dir, music_dir, docs_dir]
    
    console.print("\n")
    console.rule("[bold cyan]📁 Choose Download Location[/bold cyan]")
    console.print()
    console.print("[yellow]Where would you like to save your downloaded music?[/yellow]")
    console.print()
    
    # Show suggested locations in a table
    table = Table(title="Suggested Locations", show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Location", style="green")
    table.add_column("Description", style="dim")
    
    suggestions = []
    for idx, dir_path in enumerate(common_dirs, 1):
        exists = "✓ exists" if os.path.exists(dir_path) else "will be created"
        suggestions.append(dir_path)
        
        # Shorten path for display
        display_path = dir_path.replace(home_dir, "~")
        
        if idx == 1:
            desc = f"Default location ({exists})"
        elif 'Music' in dir_path:
            desc = f"Your Music folder ({exists})"
        else:
            desc = f"Your Documents folder ({exists})"
        
        table.add_row(str(idx), display_path, desc)
    
    # Add custom option
    table.add_row("4", "[bold]Custom path[/bold]", "Enter your own path")
    
    console.print(table)
    console.print()
    
    while True:
        choice = Prompt.ask(
            "[bold green]Choose option[/bold green]",
            choices=["1", "2", "3", "4"],
            default="1"
        )
        
        if choice in ["1", "2", "3"]:
            selected_path = suggestions[int(choice) - 1]
            
            # Show full path
            console.print(f"\n[cyan]Selected: [bold]{selected_path}[/bold][/cyan]")
            
            # Create if doesn't exist
            if not os.path.exists(selected_path):
                if Confirm.ask(f"[yellow]Folder doesn't exist. Create it?[/yellow]", default=True):
                    try:
                        os.makedirs(selected_path, exist_ok=True)
                        console.print(f"[green]✓ Created folder: {selected_path}[/green]")
                        return selected_path
                    except Exception as e:
                        console.print(f"[red]✗ Error creating folder: {e}[/red]")
                        console.print("[yellow]Please try again with a different path.[/yellow]")
                        continue
                else:
                    console.print("[yellow]Please choose a different location.[/yellow]")
                    continue
            else:
                return selected_path
                
        elif choice == "4":
            # Custom path input
            console.print()
            console.print("[dim]Examples:[/dim]")
            console.print(f"  [dim]- {os.path.join(home_dir, 'MyMusic')}[/dim]")
            console.print(f"  [dim]- /mnt/external/Music[/dim]")
            console.print(f"  [dim]- ~/Downloads/Playlists[/dim]")
            console.print()
            
            custom_path = Prompt.ask("[bold]Enter full path[/bold]").strip()
            
            # Expand ~ to home directory
            custom_path = os.path.expanduser(custom_path)
            custom_path = os.path.abspath(custom_path)
            
            # Validate path
            try:
                # Check if parent exists
                parent_dir = os.path.dirname(custom_path)
                if not os.path.exists(parent_dir):
                    console.print(f"[red]✗ Parent directory doesn't exist: {parent_dir}[/red]")
                    if Confirm.ask("[yellow]Try again?[/yellow]", default=True):
                        continue
                    else:
                        return None
                
                # Create the folder
                if not os.path.exists(custom_path):
                    if Confirm.ask(f"[yellow]Create folder: {custom_path}?[/yellow]", default=True):
                        os.makedirs(custom_path, exist_ok=True)
                        console.print(f"[green]✓ Created folder: {custom_path}[/green]")
                        return custom_path
                    else:
                        if Confirm.ask("[yellow]Try again?[/yellow]", default=True):
                            continue
                        else:
                            return None
                else:
                    console.print(f"[green]✓ Using existing folder: {custom_path}[/green]")
                    return custom_path
                    
            except Exception as e:
                console.print(f"[red]✗ Invalid path: {e}[/red]")
                if Confirm.ask("[yellow]Try again?[/yellow]", default=True):
                    continue
                else:
                    return None


def select_download_folder(use_gui: bool = True) -> Optional[str]:
    """
    Main function to select download folder.
    Tries GUI first, falls back to CLI if GUI not available or user prefers CLI.
    
    Args:
        use_gui: Whether to try GUI dialog first (default: True)
        
    Returns:
        Selected folder path or None if cancelled
    """
    folder_path = None
    
    # Try GUI first if requested
    if use_gui:
        print("Opening folder selection dialog...")
        folder_path = select_folder_gui()
        
        if folder_path:
            # Validate and create if needed
            try:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                    print(f"✓ Created folder: {folder_path}")
                else:
                    print(f"✓ Selected folder: {folder_path}")
                return folder_path
            except Exception as e:
                print(f"✗ Error with selected folder: {e}")
                print("Falling back to command-line selection...")
                folder_path = None
    
    # Use CLI if GUI failed or not requested
    if not folder_path:
        folder_path = select_folder_cli()
    
    return folder_path


def main():
    """Test/demo the folder selector."""
    from rich.console import Console
    
    console = Console()
    console.print("\n[bold magenta]Folder Selector Demo[/bold magenta]\n")
    
    # Let user choose method
    from rich.prompt import Prompt
    method = Prompt.ask(
        "Selection method",
        choices=["gui", "cli", "auto"],
        default="auto"
    )
    
    if method == "gui":
        folder = select_folder_gui()
    elif method == "cli":
        folder = select_folder_cli()
    else:
        folder = select_download_folder(use_gui=True)
    
    if folder:
        console.print(f"\n[green]✓ Selected folder: [bold]{folder}[/bold][/green]")
    else:
        console.print("\n[yellow]No folder selected[/yellow]")


if __name__ == "__main__":
    main()
