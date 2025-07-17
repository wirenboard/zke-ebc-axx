# /home/boger/work/board/zke_ebc_axx/update_stored_charge.py
import csv

# Define the input and output file
input_file = "night3.csv"
output_file = "night3_updated.csv"

# Read the CSV file, update the stored_charge, and write to a new file
with open(input_file, 'r') as infile, open(output_file, 'w', newline='') as outfile:
    reader = csv.DictReader(infile)
    
    # Get the fieldnames from the reader
    fieldnames = reader.fieldnames
    
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    
    # Process each row
    for row in reader:
        # Convert stored_charge to float, add 708, and convert back to string
        if "stored_charge" in row:
            try:
                row["stored_charge"] = str(float(row["stored_charge"]) + 708)
            except ValueError:
                # Handle case where stored_charge might not be a valid number
                pass
        
        writer.writerow(row)

print(f"Updated stored_charge values written to {output_file}")
