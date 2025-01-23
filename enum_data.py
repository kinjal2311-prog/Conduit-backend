enum_thermal_classification = ['','Ok', 'Nominal','Intermediate','Serious','Critical','Alert']

enum_nec_violation = ['',
                      'Circuit - Breaker is restricted from freely operating - (NEC 240.8)',
                      'Circuit - Exceeds panel limit - (NEC 408.36)',
                      'Component - Visible Corrosion',
                      'Conduit - Improperly fastened or secured - (NEC 300.11(A))',
                      'Enclosure - Missing dead front, door, cover, etc. - (NEC 110.12(A))',
                      'Enclosure - Must be free of foreign materials - (NEC 110.12(B) / NFPA 70B 13.3.2)',
                      'Enclosure - Unused opening must be sealed - (NEC 110.12 (A) / 312.5(A))',
                      'Fuse - Parallel fuses must match - (NEC 240.8)',
                      'General - Lack of component integrity',
                      'General - Not installed in a proper worklike manner',
                      'Grounding - Need earth connection - (NEC 250.4(A))',
                      'Marking/Labels - Missing or Insufficient information - (NEC 110.21(B) or 408.4)',
                      'Mechanics - Damaged/broken parts',
                      'Missing arc flash and shock hazard warning labels - (NEC 110.16(A))',
                      'Plug Fuse - Exposed energized parts - (NEC 240.50(D))',
                      'Temperature - Inadequate ventilation/cooling for component',
                      'Terminals - Connection made without damaging wire - (NEC 110.14(A))',
                      'Wire - 1 wire per terminal - (NEC 110.14(A))',
                      'Wire - Improper Neutral Conductor - (NEC 200.4(A))',
                      'Wire - Not Protected from damage - (NEC 300.4)',
                      'Wire - Size wrong for load - (NEC 210.19(A))',
                      'Wire - Wire bundle should have listed bushing',
                      'Wire - Wire burned or damaged',
                      'NEC.250.97 Bonding and Grounding']

enum_osha_violation = ['',
                       'Clearance Insufficient Access',
                       'Enclosure Broken locking mechanism',
                       'Enclosure Damaged',
                       'Enclosure Should be waterproof',
                       'Equipment Free of Hazards',
                       'Grounding Must be permanent continuous',
                       'Lighting Inadequate around equipment',
                       'Marking Labels Inadequate or missing information on equipment',
                       'Mounting Should be secure',
                       'Noise Excessive',
                       'Wire Exposed']

enum_thermal_anomaly_probable_cause = ['',
                                       'Internal Flaw',
                                       'Overload',
                                       'Poor Connection']

enum_thermal_anomaly_recommendation = ['',
                                       'Contiue to Monitor',
                                       'Replace Component',
                                       'Verify, Clean and Tighten']
enum_maintenance_condition_index_type = ['',      
                                        'Serviceable',
                                        'Limited',
                                        'Non-Serviceable']

enum_woline_temp_issue_type=['',
                            'Code',
                            'Thermal',
                            'Repair',
                            'Replace',
                            '',
                            'Other',
                            '',
                            '',
                            'Ultrasonic']

enum_temp_panel_schedule_type=['',
                            'Current',
                            'Needs Updating',
                            'Missing']

enum_temp_ultrasonic_issue_type = ['',
                                  'Crack',
                                  'Void',
                                  'Delamination',
                                  'Inclusions',
                                  'Corrosion',
                                  'Porosity']
enum_severity_criteria_type = ['',
                            'Similar',
                            'Ambient',
                            'Indirect']
enum_arc_flash_label = ['',
                        'Yes',
                        'No',
                        'Missing']

enum_nfpa_violation_type = ['',
                            'Chapter 11.3.2 Power and Distribution transformer Cleaning',
                            'Chapter 11.3.1 Visual Inspections',
                            'Chapter 12.3.2 Substations and Switchgear Cleaning',
                            'Chapter 12.3.1 Visual Inspections',
                            'Chapter 13.3.2 Panelboards and Switchboards Cleaning',
                            'Chapter 13.3.1 Visual Inspections',
                            'Chapter 15.3.2 Circuit Breakers Low- and Medium Voltage',
                            'Chapter 15.3.1 Visual Inspections',
                            'Chapter 25.3.2 UPS Cleaning',
                            'Chapter 25.3.1 Visual Inspections',
                            'Chapter 28.3.2 Motor Control Equipment Cleaning',
                            'Chapter 28.3.1 Visual Inspections']
