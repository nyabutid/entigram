from PIL import Image, ImageDraw, ImageFont
import os

# Configuration
WIDTH, HEIGHT = 1200, 900
BG_COLOR = (13, 17, 23)    # GitHub Dark Mode
BLUE = (88, 166, 255)      # Primary Blue (Broker)
GREEN = (35, 134, 54)      # Domain Green (Operational)
AMBER = (210, 153, 34)     # Warning/Amber (Finance/HR)
AGENT_COLOR = (187, 128, 255) # Purple (The Agentic Layer)
GRAY = (48, 54, 61)        # Border Gray
TEXT_COLOR = (201, 209, 217)

def generate_agentic_bridge():
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 1. Draw Subtle Grid
    grid_spacing = 60
    for x in range(0, WIDTH, grid_spacing):
        draw.line([(x, 0), (x, HEIGHT)], fill=(22, 27, 34), width=1)
    for y in range(0, HEIGHT, grid_spacing):
        draw.line([(0, y), (WIDTH, y)], fill=(22, 27, 34), width=1)

    # 2. Central Broker Node
    cx, cy = WIDTH // 2, HEIGHT // 2 + 100
    r_center = 75
    
    # 3. Peripheral Domain Nodes
    # (x_offset, y_offset, color, label, sublabel)
    nodes = {
        "Salesforce": (cx-350, cy-150, GREEN, "Salesforce", "CRM"),
        "Workday": (cx+350, cy-150, AMBER, "Workday", "HR"),
        "Stripe": (cx-350, cy+150, AMBER, "Stripe", "Finance"),
        "Jira": (cx+350, cy+150, GREEN, "Jira", "Product"),
        "GitHub": (cx, cy-300, BLUE, "GitHub", "IT / Dev"),
    }

    try:
        font_main = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
        font_sub = ImageFont.truetype("/System/Library/Fonts/Monaco.ttf", 14)
        font_header = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 52)
        font_agent = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_agent = ImageFont.load_default()

    # Draw Infrastructure Connections (Broker to Domains)
    for name, (nx, ny, color, label, sub) in nodes.items():
        draw.line([(nx, ny), (cx, cy)], fill=GRAY, width=1)

    # Draw Domain Circles
    for name, (nx, ny, color, label, sub) in nodes.items():
        r = 65
        draw.ellipse([nx-r, ny-r, nx+r, ny+r], outline=color, width=2, fill=BG_COLOR)
        draw.text((nx, ny - 10), label, fill=TEXT_COLOR, anchor="mm", font=font_main)
        draw.text((nx, ny + 20), f"[{sub}]", fill=color, anchor="mm", font=font_sub)

    # 4. The Entigram-Aware AI Agent
    # Positioned between Salesforce and GitHub to show "Touching 2 Domains"
    ax, ay = cx - 180, cy - 240
    
    # Draw Agent "Cerebrum" (Diamond)
    draw.polygon([(ax, ay-60), (ax+70, ay), (ax, ay+60), (ax-70, ay)], outline=AGENT_COLOR, width=4, fill=(35, 30, 45))
    
    # Agent Connections
    # Touching Domain 1: Salesforce
    draw.line([(ax, ay), (nodes["Salesforce"][0], nodes["Salesforce"][1])], fill=AGENT_COLOR, width=2)
    # Touching Domain 2: GitHub
    draw.line([(ax, ay), (nodes["GitHub"][0], nodes["GitHub"][1])], fill=AGENT_COLOR, width=2)
    # Entigram Aware: Connection to Broker
    draw.line([(ax, ay), (cx, cy)], fill=AGENT_COLOR, width=2, dash=(10, 5))
    
    # Agent Label
    draw.text((ax, ay - 5), "AI AGENT", fill=AGENT_COLOR, anchor="mm", font=font_agent)
    draw.text((ax, ay + 20), "Entigram Aware", fill=AGENT_COLOR, anchor="mm", font=font_sub)

    # Re-draw center Broker (On top)
    draw.ellipse([cx-r_center, cy-r_center, cx+r_center, cy+r_center], outline=BLUE, width=4, fill=BG_COLOR)
    draw.text((cx, cy - 10), "Entigram", fill=BLUE, anchor="mm", font=font_main)
    draw.text((cx, cy + 20), "Broker", fill=BLUE, anchor="mm", font=font_sub)

    # Header
    draw.text((WIDTH//2, 80), "The Agentic Enterprise", fill=TEXT_COLOR, anchor="mm", font=font_header)
    draw.text((WIDTH//2, 140), "DETERMINISTIC STATE FOR AUTONOMOUS REASONING", fill=GRAY, anchor="mm", font=font_sub)

    # Save to Downloads
    output_path = os.path.expanduser("~/Downloads/entigram_agentic_enterprise.png")
    img.save(output_path)
    print(f"✅ Refined Agentic visual generated at: {output_path}")

if __name__ == "__main__":
    generate_agentic_bridge()
