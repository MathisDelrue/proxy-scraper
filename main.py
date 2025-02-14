import asyncio
import aiohttp
import re
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import os
import platform

console = Console()

def clear_screen():
    """Clear the terminal screen based on the operating system"""
    if platform.system().lower() == "windows":
        os.system('cls')
    else:
        os.system('clear')

class ProxyScraper:
    def __init__(self):
        self.http_proxies = set()
        self.socks4_proxies = set()
        self.socks5_proxies = set()
        self.checked_count = 0
        self.start_time = None
        self.sources = [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        ]
        
        # Ensure output directory and files exist
        self.setup_output_files()

    def setup_output_files(self):
        """Create output directory and required files if they don't exist"""
        # Create output directory
        os.makedirs("output", exist_ok=True)
        
        # Required output files
        required_files = ["http.txt", "socks4.txt", "socks5.txt"]
        
        # Check and create files if they don't exist
        for filename in required_files:
            file_path = os.path.join("output", filename)
            if not os.path.exists(file_path):
                with open(file_path, "w") as f:
                    f.write("")  # Create empty file
                console.print(f"[yellow]Created missing file: {filename}[/yellow]")

    async def fetch_proxies(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    content = await response.text()
                    proxies = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', content)
                    
                    if 'socks4' in url.lower():
                        self.socks4_proxies.update(proxies)
                    elif 'socks5' in url.lower():
                        self.socks5_proxies.update(proxies)
                    else:
                        self.http_proxies.update(proxies)
        except Exception as e:
            console.print(f"[red]Error fetching from {url}: {str(e)}[/red]")

    async def check_proxy(self, proxy, proxy_type):
        try:
            check_url = "http://www.google.com"
            timeout = aiohttp.ClientTimeout(total=5)  # Reduced timeout to 5 seconds
            
            connector = None
            if proxy_type == "http":
                connector = aiohttp.TCPConnector(ssl=False)
            else:
                connector = aiohttp.TCPConnector(ssl=False)

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(
                    check_url,
                    proxy=f"{proxy_type}://{proxy}",
                    allow_redirects=True
                ) as response:
                    if response.status == 200:
                        return proxy, True
        except:
            pass
        return proxy, False

    def save_proxies(self, proxies, filename):
        """Save proxies to file, clearing previous content"""
        with open(f"output/{filename}", "w") as f:
            for proxy in proxies:
                f.write(f"{proxy}\n")

    def get_elapsed_time(self):
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            minutes = elapsed.seconds // 60
            seconds = elapsed.seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"

    async def check_proxies(self, proxies, proxy_type, progress, task):
        chunk_size = 100  # Number of proxies to check simultaneously
        working_proxies = set()
        
        for i in range(0, len(proxies), chunk_size):
            chunk = list(proxies)[i:i + chunk_size]
            tasks = []
            for proxy in chunk:
                tasks.append(self.check_proxy(proxy, proxy_type))
            
            results = await asyncio.gather(*tasks)
            for proxy, is_working in results:
                if is_working:
                    working_proxies.add(proxy)
                self.checked_count += 1
                progress.update(
                    task,
                    advance=1,
                    elapsed=self.get_elapsed_time(),
                    checked=self.checked_count,
                    remaining=self.total_proxies - self.checked_count
                )
        
        return working_proxies

    async def main(self):
        self.start_time = datetime.now()
        clear_screen()
        console.print(Panel.fit(
            "[bold cyan]Proxy Scraper and Checker[/bold cyan]",
            border_style="blue"
        ))

        # Scraping phase
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Scraping proxies...", total=len(self.sources))
            
            tasks = []
            for source in self.sources:
                tasks.append(self.fetch_proxies(source))
                progress.advance(task)
            await asyncio.gather(*tasks)

        # Display initial counts
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Proxy Type", style="cyan")
        table.add_column("Count", justify="right", style="green")
        
        table.add_row("HTTP", str(len(self.http_proxies)))
        table.add_row("SOCKS4", str(len(self.socks4_proxies)))
        table.add_row("SOCKS5", str(len(self.socks5_proxies)))
        
        console.print("\n[bold cyan]Initial Proxy Count:[/bold cyan]")
        console.print(table)

        # Checking phase
        console.print("\n[bold cyan]Checking proxies...[/bold cyan]")
        self.total_proxies = len(self.http_proxies) + len(self.socks4_proxies) + len(self.socks5_proxies)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]Elapsed: {task.fields[elapsed]}"),
            TextColumn("[yellow]Checked: {task.fields[checked]}/{task.fields[total_proxies]}"),
            TextColumn("[green]Remaining: {task.fields[remaining]}"),
            console=console
        ) as progress:
            # Check HTTP proxies
            http_task = progress.add_task(
                "[cyan]Checking HTTP proxies...", 
                total=len(self.http_proxies),
                elapsed="00:00",
                checked=0,
                total_proxies=self.total_proxies,
                remaining=self.total_proxies
            )
            working_http = await self.check_proxies(self.http_proxies, "http", progress, http_task)

            # Check SOCKS4 proxies
            socks4_task = progress.add_task(
                "[cyan]Checking SOCKS4 proxies...", 
                total=len(self.socks4_proxies),
                elapsed="00:00",
                checked=self.checked_count,
                total_proxies=self.total_proxies,
                remaining=self.total_proxies - self.checked_count
            )
            working_socks4 = await self.check_proxies(self.socks4_proxies, "socks4", progress, socks4_task)

            # Check SOCKS5 proxies
            socks5_task = progress.add_task(
                "[cyan]Checking SOCKS5 proxies...", 
                total=len(self.socks5_proxies),
                elapsed="00:00",
                checked=self.checked_count,
                total_proxies=self.total_proxies,
                remaining=self.total_proxies - self.checked_count
            )
            working_socks5 = await self.check_proxies(self.socks5_proxies, "socks5", progress, socks5_task)

        # Save working proxies
        self.save_proxies(working_http, "http.txt")
        self.save_proxies(working_socks4, "socks4.txt")
        self.save_proxies(working_socks5, "socks5.txt")

        # Display final results
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Proxy Type", style="cyan")
        table.add_column("Working", justify="right", style="green")
        table.add_column("Total", justify="right", style="yellow")
        
        table.add_row("HTTP", str(len(working_http)), str(len(self.http_proxies)))
        table.add_row("SOCKS4", str(len(working_socks4)), str(len(self.socks4_proxies)))
        table.add_row("SOCKS5", str(len(working_socks5)), str(len(self.socks5_proxies)))
        
        console.print("\n[bold cyan]Final Results:[/bold cyan]")
        console.print(table)
        
        console.print(f"\n[yellow]Total Time: {self.get_elapsed_time()}[/yellow]")
        console.print(f"[yellow]Total Proxies Checked: {self.checked_count}[/yellow]")
        console.print("\n[green]Proxies have been saved to the output directory![/green]")

if __name__ == "__main__":
    clear_screen()
    try:
        scraper = ProxyScraper()
        asyncio.run(scraper.main())
    except KeyboardInterrupt:
        console.print("\n[red]Scraper stopped by user[/red]")
    except Exception as e:
        console.print(f"\n[red]An error occurred: {str(e)}[/red]")
