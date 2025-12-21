#!/bin/bash
# Demo script to test the optical diagnostics parser end-to-end

set -e

# Configuration
DEVICE="10.209.3.39"
TEST_XML="parsers/test_data/optics_rpc_response.xml"
OUTPUT_DIR="./test_output"
PUSHGATEWAY_URL="http://localhost:9091"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Junos Optical Diagnostics Parser Demo ===${NC}\n"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Step 1: Parse XML to JSON
echo -e "${GREEN}Step 1: Parsing XML to JSON...${NC}"
python3 parsers/optics_diagnostics.py \
  --input "$TEST_XML" \
  --output "$OUTPUT_DIR/metrics.json" \
  --device "$DEVICE" \
  --format json

echo "✓ JSON output created at $OUTPUT_DIR/metrics.json"
echo ""

# Step 2: Display results
echo -e "${GREEN}Step 2: Displaying parsed metrics...${NC}"
echo ""
echo "Interface count: $(jq '.interfaces | length' $OUTPUT_DIR/metrics.json)"
echo "Lane count: $(jq '.lanes | length' $OUTPUT_DIR/metrics.json)"
echo ""

echo "Sample lane metrics:"
jq '.lanes[0]' $OUTPUT_DIR/metrics.json
echo ""

echo "Sample interface metrics:"
jq '.interfaces[0] | {if_name, temperature_high_alarm, voltage_high_alarm, tx_power_high_alarm}' $OUTPUT_DIR/metrics.json
echo ""

# Step 3: Test with metadata
echo -e "${GREEN}Step 3: Testing with additional metadata...${NC}"
python3 parsers/optics_diagnostics.py \
  --input "$TEST_XML" \
  --output "$OUTPUT_DIR/metrics_with_metadata.json" \
  --device "$DEVICE" \
  --format json \
  --metadata '{"origin_hostname":"5d2-qfx1-leaf2","blueprint_label":"HW-BP","probe_label":"Optical Transceivers","stage_name":"Lane Stats"}'

echo "✓ JSON with metadata created"
echo ""
echo "Lane metrics with metadata:"
jq '.lanes[0] | {if_name, lane, rx_power, tx_power, origin_hostname, probe_label}' $OUTPUT_DIR/metrics_with_metadata.json
echo ""

# Step 4: Convert to Prometheus format (optional)
echo -e "${GREEN}Step 4: Converting to Prometheus line protocol...${NC}"
if command -v python3 &> /dev/null; then
  # Simple conversion using jq
  jq -r '.lanes[] | 
    "junos_optics_rx_power_dbm{device=\"\(.device)\",interface=\"\(.if_name)\",lane=\"\(.lane)\"} \(.rx_power)\n" +
    "junos_optics_tx_power_dbm{device=\"\(.device)\",interface=\"\(.if_name)\",lane=\"\(.lane)\"} \(.tx_power)\n" +
    "junos_optics_tx_bias_milliamps{device=\"\(.device)\",interface=\"\(.if_name)\",lane=\"\(.lane)\"} \(.tx_bias)"
  ' $OUTPUT_DIR/metrics.json > $OUTPUT_DIR/metrics.prom
  
  echo "✓ Prometheus format created at $OUTPUT_DIR/metrics.prom"
  echo ""
  echo "Sample Prometheus metrics:"
  head -n 5 $OUTPUT_DIR/metrics.prom
  echo ""
fi

# Step 5: Run tests
echo -e "${GREEN}Step 5: Running test suite...${NC}"
cd parsers && python3 test_optics_diagnostics.py
cd ..
echo ""

# Step 6: Optional - Push to Prometheus (if available)
if curl -s "$PUSHGATEWAY_URL" > /dev/null 2>&1; then
  echo -e "${GREEN}Step 6: Pushing to Prometheus Pushgateway...${NC}"
  python3 scripts/push_to_prometheus.py \
    --pushgateway "$PUSHGATEWAY_URL" \
    --job "junos_telemetry_test" \
    --instance "$DEVICE" \
    --metrics-file "$OUTPUT_DIR/metrics.json" \
    --format json
  echo ""
else
  echo -e "${BLUE}Step 6: Skipping Prometheus push (Pushgateway not available at $PUSHGATEWAY_URL)${NC}"
  echo "To test pushing, start Pushgateway: docker run -d -p 9091:9091 prom/pushgateway"
  echo ""
fi

echo -e "${GREEN}=== Demo Complete ===${NC}"
echo "Output files:"
echo "  - $OUTPUT_DIR/metrics.json"
echo "  - $OUTPUT_DIR/metrics_with_metadata.json"
echo "  - $OUTPUT_DIR/metrics.prom"
echo ""
echo "Next steps:"
echo "  1. Review the JSON output: cat $OUTPUT_DIR/metrics.json | jq"
echo "  2. Run the full Ansible playbook: ansible-playbook -i inventory.yml junos_telemetry.yml"
echo "  3. Set up Prometheus to scrape the Pushgateway"
