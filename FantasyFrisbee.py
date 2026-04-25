import requests
from bs4 import BeautifulSoup
import csv
import sys
import os.path
import json

def get_roster_dict_by_owner(json_filepath):
    """
    Parses the rosters JSON and returns a dictionary where keys are owner names.
    The first element of each list is 'owner, first_pdga_number'.
    """
    with open(json_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    owner_dict = {}
    
    for team in data.get('teams', []):
        owner = team.get('owner')
        players = team.get('players', [])
        
        if not owner or not players:
            continue
            
        # Extract all PDGA numbers for the team
        pdga_numbers = [str(p.get('pdga_number')) for p in players]
        
        # Format the first element as requested: 'owner, pdga_number'
        # Example: 'Adam, 91249'
        first_entry = pdga_numbers[0]
        
        # Construct the final list for this owner
        # The first element is the special string, followed by the rest of the IDs
        owner_dict[owner] = [first_entry] + pdga_numbers[1:]
            
    return owner_dict

def get_roster_pdga_numbers(json_filepath):
    """
    Reads the rosters JSON and returns a list of all player PDGA numbers as strings.
    """
    with open(json_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    pdga_numbers = []
    for team in data.get('teams', []):
        for player in team.get('players', []):
            # Store as string to match the scraper's text output
            pdga_numbers.append(str(player.get('pdga_number')))
            
    return pdga_numbers

def scrape_pdga_mpo_results(event_id,valid_pdga_numbers):
    # Construct the URL based on the event ID
    url = f"https://www.pdga.com/tour/event/{event_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the page for event {event_id}: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. Locate the MPO division heading
    mpo_heading = soup.find(id='MPO')
    
    if not mpo_heading:
        print(f"Could not find the MPO division on the page for event {event_id}.")
        return
        
    # 2. The heading is nested inside a <details> tag that contains the whole MPO section.
    # We find that parent container so we only search within it.
    mpo_section = mpo_heading.find_parent('details')
    
    # 3. Find the results table inside that specific MPO section
    results_table = mpo_section.find('table', class_='results')
    
    if not results_table:
        print(f"Could not find the results table inside the MPO section for event {event_id}.")
        return

    # Prepare file for writing
    filename = f"Tournament_results/pdga_event_{event_id}_MPO_results.csv"
    headers_html = results_table.find_all('th')
    header_labels = ['Team Owner'] + [th.get_text(strip=True) for th in headers_html]
    pdga_idx = header_labels.index('PDGA#')-1
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(header_labels) # Write the headers

        rows = results_table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if cols:
                row_data = [ele.get_text(strip=True) for ele in cols]         
                # Only write the row if the player's PDGA # is in our list
                for key in valid_pdga_numbers:
                    if row_data[pdga_idx] in valid_pdga_numbers[key]:
                        row_data = [key] + [ele.get_text(strip=True) for ele in cols]
                        writer.writerow(row_data)

    print(f"Successfully wrote MPO results to {filename}")

def load_tournaments_to_array(filepath):
    """
    Reads a comma-separated text file of tournaments and returns an array of dictionaries.
    """
    tournaments = []
    
    if not os.path.exists(filepath):
        print(f"Error: The file '{filepath}' could not be found.")
        return tournaments

    with open(filepath, 'r', encoding='utf-8') as file:
        week_no = 1
        for line in file:
            # Clean up the line (removes newlines and the artifact '')
            clean_line = line.replace('', '').strip()
            
            # Skip empty lines
            if not clean_line:
                continue
                
            # Split the line by commas
            parts = clean_line.split(',')
            
            # The last element might be an empty string because of the trailing comma
            if len(parts) >= 2:
                event_id = parts[0].strip()
                name = parts[1].strip()
                tier = parts[2].strip() if len(parts) > 2 else ""
                
                # Append as a dictionary for easy access later
                tournaments.append({
                    'event_id': event_id,
                    'name': name,
                    'tier': tier,
                    'week': week_no
                })
            week_no += 1
                
    return tournaments

def event_score(named_roster, tournaments_array):
    """
    named_roster: Dictionary keyed by owner name.
    tournaments_array: List of dictionaries with 'event_id', 'name', and 'tier'.
    """
    output_file = "total_score.csv"
    underdogs = ["131546", "145206"]
    owners = sorted(named_roster.keys())
    
    print(f"--- Starting Scoring Process ---")
    print(f"Targeting owners: {', '.join(owners)}")

    with open(output_file, mode='w', newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["Event Name", "Event Multiplier"] + owners)

        for tourney in tournaments_array:
            event_id = tourney['event_id']
            event_name = tourney['name']
            tier = tourney['tier'].upper()

            # 1. Determine Event Multiplier
            if tier == "M":
                multiplier = 2.0
            elif tier in ["ESP", "P"]:
                multiplier = 1.5
            else:
                multiplier = 1.0

            print(f"\nProcessing: {event_name} (ID: {event_id})")
            print(f"  > Tier: {tier} | Multiplier: {multiplier}x")

            # 2. Locate the specific results file
            file_path = f"Tournament_results/pdga_event_{event_id}_MPO_results.csv"
            
            if not os.path.exists(file_path):
                print(f"  > [SKIP] No results file found at {file_path}")
                continue

            event_team_data = {owner: [] for owner in owners}

            with open(file_path, mode='r', encoding='utf-8') as f_in:
                reader = csv.DictReader(f_in)
                for row in reader:
                    owner = row['Team Owner']
                    pdga_num = row['PDGA#']
                    player_name = row.get('Name', 'Unknown')
                    
                    try:
                        # Convert 'T10' or '10' to float
                        place_val = float(row['Place'].replace('T', ''))
                    except (ValueError, KeyError):
                        continue

                    # 3. Apply Underdog Bonus
                    if pdga_num in underdogs:
                        original_place = place_val
                        place_val *= 0.5
                        print(f"  > [BONUS] {player_name} ({owner}) | Orig: {original_place} -> Adjusted: {place_val}")
                    
                    if owner in event_team_data:
                        event_team_data[owner].append(place_val)

            # 4. Calculate Team Totals
            row_results = [event_name, multiplier]
            for owner in owners:
                scores = event_team_data[owner]
                print(f"  > Team {owner} raw adjusted scores: {scores}")
                
                if len(scores) >= 3:
                    scores.sort()
                    top_three = scores[:3]
                    best_three_sum = sum(top_three)
                    final_score = round(best_three_sum * multiplier, 2)
                    
                    print(f"    - Counting: {top_three} | Subtotal: {best_three_sum} | Final (x{multiplier}): {final_score}")
                    row_results.append(final_score)
                else:
                    print(f"    - Not enough players (Found {len(scores)}/3). Score: 0")
                    row_results.append(0)

            writer.writerow(row_results)

def write_cumulative_scores(input_file,output_file):
    """
    Reads total_score.csv and writes a running total for each week to cum_score.csv.
    Format: Week Number, Adam Cumulative, Greg Cumulative
    """
    running_adam = 0.0
    running_greg = 0.0
    week_number = 1

    print(f"Reading event scores from {input_file}...")

    # Open the input and output files
    with open(input_file, mode='r', encoding='utf-8') as f_in, \
         open(output_file, mode='w', newline='', encoding='utf-8') as f_out:
        
        reader = csv.DictReader(f_in)
        writer = csv.writer(f_out)
        
        # Write headers for the cumulative file
        writer.writerow(["Week", "Adam", "Greg"])

        for row in reader:
            try:
                # Add the current event scores to the running totals
                running_adam += float(row['Adam'])
                running_greg += float(row['Greg'])
                
                # Write the current week's cumulative totals
                writer.writerow([week_number, round(running_adam, 2), round(running_greg, 2)])
                
                print(f"Week {week_number}: Adam {round(running_adam, 2)}, Greg {round(running_greg, 2)}")
                
                week_number += 1
            except (ValueError, KeyError) as e:
                print(f"Skipping a row due to error: {e}")
                continue

    print(f"Successfully wrote weekly cumulative scores to {output_file}")

def update_roster(rosters_path="rosters.json", tournaments_array=[], results_dir="Tournament_results"):
    """
    Updates rosters.json with player stats.
    tournaments_array: List of dicts, each containing a 'week' key.
    """
    # 1. Load the current roster data
    with open(rosters_path, 'r', encoding='utf-8') as f:
        roster_data = json.load(f)

    underdogs = ["131546", "145206"]
    
    # Identify the highest week number available in the tournament list
    max_weeks = len(tournaments_array)

    print(f"Updating roster stats for {max_weeks} weeks...")

    for team in roster_data.get('teams', []):
        owner = team.get('owner')
        
        for player in team.get('players', []):
            pdga_num = str(player.get('pdga_number'))
            
            # Reset stats for fresh calculation
            weekly_scores = []
            tournaments_played = 0
            times_counted = 0
            season_total = 0.0

            # 2. Iterate through every week defined in the tournament list
            for tourney in tournaments_array:
                event_id = tourney['event_id']
                # We expect the file naming convention we established earlier
                file_path = os.path.join(results_dir, f"pdga_event_{event_id}_MPO_results.csv")
                
                player_score_this_week = None
                team_scores_this_week = []

                if os.path.exists(file_path):
                    with open(file_path, mode='r', encoding='utf-8') as f_in:
                        reader = csv.DictReader(f_in)
                        for row in reader:
                            try:
                                # Standardize the 'Place' column
                                raw_place = float(row['Place'].replace('T', ''))
                                
                                # If this row belongs to the player's owner, track for "Times Counted"
                                if row['Team Owner'] == owner:
                                    # Underdog logic for team comparison only
                                    adj_score = raw_place * 0.5 if row['PDGA#'] in underdogs else raw_place
                                    team_scores_this_week.append(adj_score)
                                    
                                    # Check if this is the specific player
                                    if row['PDGA#'] == pdga_num:
                                        player_score_this_week = raw_place
                            except (ValueError, KeyError):
                                continue

                # 3. Process the week results for the player
                if player_score_this_week is not None:
                    weekly_scores.append(player_score_this_week)
                    tournaments_played += 1
                    season_total += player_score_this_week
                    
                    # Sort team scores to see if this player was in the best 3
                    team_scores_this_week.sort()
                    # Apply underdog bonus to player's specific comparison score
                    my_comparison_score = player_score_this_week * 0.5 if pdga_num in underdogs else player_score_this_week
                    
                    if my_comparison_score in team_scores_this_week[:3]:
                        times_counted += 1
                else:
                    # Player did not play or file doesn't exist yet
                    weekly_scores.append("x")

            # 4. Update the JSON object
            player['weekly_scores'] = weekly_scores
            player['tournaments_played'] = tournaments_played
            player['times_counted'] = times_counted
            player['season_total'] = round(season_total, 2)

    # Save the updated data back to the file
    with open(rosters_path, 'w', encoding='utf-8') as f:
        json.dump(roster_data, f, indent=2)
        
    print(f"Roster update complete. Check {rosters_path} for updated stats.")

if __name__ == "__main__":
    filename = 'Tournaments.txt'
    tournaments_array = load_tournaments_to_array(filename)
    print(tournaments_array)
    roster_pdga_numbers = get_roster_pdga_numbers('rosters.json')
    print(roster_pdga_numbers)
    # Two rosters, one named Adam, one named Greg. 
    named_roster = get_roster_dict_by_owner('rosters.json')
    week_number = 5
    for t in tournaments_array[:week_number]:
        scrape_pdga_mpo_results(t['event_id'],named_roster)
    event_score(named_roster,tournaments_array)
    write_cumulative_scores("total_score.csv","cum_score.csv")
    update_roster("rosters.json", tournaments_array)
    