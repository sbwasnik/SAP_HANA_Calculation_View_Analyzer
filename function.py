# function.py
# This file contains the core logic for parsing the XML and
# generating the Graphviz DOT string for visualization.

import xml.etree.ElementTree as ET
import pandas as pd
import re
import graphviz


def analyze_cv(xml_content):
    """
    Parses a calculation view XML string and extracts key details, including
    new details about joins, filters, and calculated attributes.
    
    Args:
        xml_content (str): The content of the .calculationview file as a string.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    
    try:
        # Use ElementTree to parse the XML string
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        # Raise a detailed error if parsing fails
        raise ValueError(f"XML parsing failed: {e}")

    # Define the namespaces to correctly find elements
    ns = {"Calculation": "http://www.sap.com/ndb/BiModelCalculation.ecore"}

    # --- Section 1: General Information ---
    # Extract high-level attributes from the root element.
    metadata_element = root.find("metadata")
    general_info = {
        "id": root.attrib.get("id"),
        "type": root.attrib.get("dataCategory"),
        "visibility": root.attrib.get("visibility"),
        "calculationScenarioType": root.attrib.get("calculationScenarioType"),
        "outputViewType": root.attrib.get("outputViewType"),
        "changedAt": metadata_element.attrib.get("changedAt") if metadata_element is not None else "N/A",
    }

    # --- Section 2: Data Sources ---
    # Find all DataSource elements and extract their details.
    data_sources = []
    # The 'dataSources' element is a direct child of the root and has no namespace prefix.
    # Its children, 'DataSource', have the 'Calculation' namespace.
    data_sources_element = root.find("dataSources")
    if data_sources_element is not None:
        for source in data_sources_element.findall("DataSource"):
            
            source_id = source.attrib.get("id")
            source_type = source.attrib.get("type")
            
            source_name = ""
            source_schema = ""
            
            # Extract the specific name and schema based on the source type.
            if source_type == "DATA_BASE_TABLE":
                column_object = source.find("columnObject")
                if column_object is not None:
                    source_name = column_object.attrib.get("columnObjectName")
                    source_schema = column_object.attrib.get("schemaName")
            elif source_type == "CALCULATION_VIEW":
                # The name is derived from the last part of the resourceUri
                resource_uri = source.find("resourceUri")
                if resource_uri is not None:
                    # Split the URI by '/' and take the last element
                    source_name = resource_uri.text.split('/')[-1]
                    source_schema = "/".join(resource_uri.text.split('/')[1:-1])

            data_sources.append({
                                "ID": source_id,
                                "Name": source_name,
                                "Type": source_type,
                                "Schema": source_schema
                                 })

    data_sources_df = pd.DataFrame(data_sources)
    unique_sources_df = data_sources_df.drop_duplicates(subset=['Type', 'Name', 'Schema'])

    # --- Section 3: Calculation Views (Nodes) and their logic ---
    # Iterate through all individual calculation view nodes and get their logic.
    calc_views = {}
    calculation_views_element = root.find("calculationViews")
    if calculation_views_element is not None:
        for view in calculation_views_element.findall("calculationView", ns):
            view_id = view.attrib.get("id")
            view_type = view.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}type").split(':')[-1]
            
            # Find all input nodes for the current view.
            inputs = [
                input_node.attrib.get("node").strip("#")
                for input_node in view.findall("input")
            ]
            
            # Get filter expression.
            filters = view.find("filter")
            filter_expression = filters.text if filters is not None and filters.text and filters.text.strip() else None
            
            # Get the attributes used for joining.
            join_attributes = [
                attr.attrib.get("name")
                for attr in view.findall("Calculation:joinAttribute", ns)
            ]

            # Extract join details (type, left/right tables, joinAttribute)
            join_details = []
            if view_type == 'JoinView':
                join_type = view.attrib.get("joinType")
                input_nodes = view.findall('input')
                if len(input_nodes) == 2:
                    left_table = input_nodes[0].attrib.get('node').strip('#')
                    right_table = input_nodes[1].attrib.get('node').strip('#')

                    # Extract join joinAttribute
                    joinAttribute_element = view.find('joinAttribute')
                    joinAttribute = (
                        joinAttribute_element.attrib.get("name")
                        if joinAttribute_element is not None
                        else ""
                    )

                    # Collect all join columns
                    join_columns = [attr.attrib.get("name") for attr in view.findall("joinAttribute")]

                    join_details.append({
                        "join_type": join_type,
                        "left_table": left_table,
                        "right_table": right_table,
                        "joinAttribute": joinAttribute,
                        "join_columns": join_columns
                    })

            
            # Extract any calculated attributes with their formulas.
            calculated_attributes = []
            calc_attrs_element = view.find("calculatedViewAttributes")
            if calc_attrs_element is not None:
                for calc_attr in calc_attrs_element.findall("calculatedViewAttribute", ns):
                    attr_id = calc_attr.attrib.get("id")
                    attr_datatype = calc_attr.attrib.get("datatype")
                    # Check for formula element before accessing .text
                    formula_element = calc_attr.find("formula")
                    attr_formula = formula_element.text if formula_element is not None else "N/A"

                    calculated_attributes.append({
                        "id": attr_id,
                        "datatype": attr_datatype,
                        "formula": attr_formula,
                    })
            
            calc_views[view_id] = {
                "type": view_type,
                "inputs": inputs,
                "filters": filter_expression,
                "join_attributes": join_attributes,
                "join_details": join_details,
                "calculated_attributes": calculated_attributes,
            }

    # --- Section 4: Logical Model (Final Output) ---
    # Analyze the final exposed attributes and measures.
    logical_model = root.find("logicalModel")
    final_attributes = []
    final_measures = []

    if logical_model is not None:
        attributes_element = logical_model.find("attributes", ns)
        if attributes_element is not None:
            for attr in attributes_element.findall("attribute", ns):
                attr_id = attr.attrib.get("id")
                description_element = attr.find("descriptions", ns)
                attr_description = description_element.attrib.get("defaultDescription", "") if description_element is not None else ""
                attributeHierarchyActive = description_element.attrib.get("attributeHierarchyActive", "false") if description_element is not None else "false"
                key_mapping = attr.find("keyMapping", ns)
                keyMapping_columnObjectName = key_mapping.attrib.get("columnObjectName", "") if key_mapping is not None else ""
                keyMapping_columnName = key_mapping.attrib.get("columnName", "") if key_mapping is not None else ""
                
                final_attributes.append({
                    "Technical ID": attr_id,
                    "Description": attr_description,
                    # "Attribute Hierarchy Active": attributeHierarchyActive,
                    # "Source Object": keyMapping_columnObjectName,
                    # "Source Column": keyMapping_columnName
                })

        measures_element = logical_model.find("baseMeasures", ns)
        if measures_element is not None:
            for measure in measures_element.findall("measure", ns):
                measure_id = measure.attrib.get("id")
                measure_agg = measure.attrib.get("aggregationType")
                description_element = measure.find("descriptions", ns)
                measure_description = description_element.attrib.get("defaultDescription", "") if description_element is not None else ""
                measure_type = measure.attrib.get("measureType", "")                
                measure_mapping = measure.find("measureMapping", ns)
                measure_mapping_columnObjectName = measure_mapping.attrib.get("columnObjectName", "") if measure_mapping is not None else ""
                measure_mapping_columnName = measure_mapping.attrib.get("columnName", "") if measure_mapping is not None else ""
                
                final_measures.append({
                    "Technical ID": measure_id,
                    "Aggregation Type": measure_agg,
                    "Description": measure_description,
                    # "Measure Type": measure_type,
                    # "Source Object": measure_mapping_columnObjectName,
                    # "Source Column": measure_mapping_columnName
                })
            
    final_output = {
        "attributes": pd.DataFrame(final_attributes),
        "measures": pd.DataFrame(final_measures),
    }

    # Return all collected data in a single dictionary.
    return {
        "general": general_info,
        "data_sources": unique_sources_df,
        "calculation_views": calc_views,
        "final_output": final_output,
    }


def generate_graphviz_dot(analysis_data):
    """
    Generates a Graphviz DOT language string from the analysis data,
    incorporating detailed information about joins and filters on the edges.
    
    Args:
        analysis_data (dict): The analysis results from analyze_cv.
        
    Returns:
        str: A string in DOT language representing the data flow.
    """
    g = graphviz.Digraph(format='png')
    g.attr(rankdir='LR', splines="ortho", pad='1', nodesep='0.5', concentrate='true')
    
    # Collect all unique nodes (views and tables)
    all_nodes = set(analysis_data["calculation_views"].keys())
    for _, row in analysis_data["data_sources"].iterrows():
        all_nodes.add(row["ID"])

    # First Pass: Define all nodes
    for node_id in all_nodes:
        source_df = analysis_data["data_sources"]
        is_data_source = source_df[source_df['ID'] == node_id]
        
        if not is_data_source.empty:
            label = f"{is_data_source.iloc[0]['Name']}\\n({is_data_source.iloc[0]['Type'].replace('DATA_BASE_TABLE','Table').replace('CALCULATION_VIEW','View')})"
            g.node(node_id, label=label, shape="cylinder", style="filled", fillcolor="yellowgreen", fontname="Helvetica")
        elif node_id in analysis_data["calculation_views"]:
            view_details = analysis_data["calculation_views"][node_id]
            view_type = view_details["type"]
            label = f"{node_id.replace('_', ' ').title()}\\n({view_type.replace('View','')})"
            g.node(node_id, label=label, shape="box", style="rounded", fontname="Helvetica")
        else:
            label = node_id.replace('_', ' ').title()
            g.node(node_id, label=label, shape='box', style='rounded', fontsize='10', height='0.5', width='2.5')
    
    # Add a special node for the final output
    output_node_id = analysis_data["general"]["id"]
    output_label = f"Output\\n({len(analysis_data['final_output']['attributes']) + len(analysis_data['final_output']['measures'])} columns)"
    g.node(output_node_id, label=output_label, shape="oval", style="rounded,filled", fillcolor="lightblue", fontname="Helvetica")

    # Second Pass: Create edges and intermediary nodes
    for view_id, details in analysis_data["calculation_views"].items():
        # Start the chain with the current view's input nodes
        input_source_nodes = details["inputs"]
        
        # Determine the final destination of this view's chain
        final_destination = view_id
        
        # Check for filter and calculated attributes
        has_filter = details.get("filters")
        has_calc_attrs = details.get("calculated_attributes")
        
        # If there's a calculated attribute, create an intermediary node for it
        if has_calc_attrs:
            calc_node_id = f"{view_id}_calc"
            calc_label = "Calculated Attributes\\n" + "\\n".join([f"{a['id']}: {a['formula']}" for a in details['calculated_attributes']])
            g.node(calc_node_id, label=calc_label, shape="note", style="filled", fillcolor="powderblue", fontname="Helvetica", fontsize='9')
            g.edge(calc_node_id, final_destination, arrowsize='0.7', color='black')
            final_destination = calc_node_id
            


        
        
        
        
        
        
        
        
        
        
        # If there's a filter, create an intermediary node for it
        if has_filter:
            filter_node_id = f"{view_id}_filter"
            if details.get("filters"):
                # Replace ' and ' with newline for better readability
                filters_text = details["filters"].replace(" and ", "\n")
                filter_label = f"(Filters)\n{filters_text}"
            else:
                filter_label = ""
            # filter_label = f"Filter\\n{details['filters']}"
            g.node(filter_node_id, label=filter_label, shape="note", style="filled", fillcolor="lightgoldenrod", fontname="Helvetica", fontsize='9')
            
            # The edge now goes from the filter to the next step (calc or final view)
            if has_calc_attrs:
                g.edge(filter_node_id, calc_node_id, arrowsize='0.7', color='black')
            else:
                g.edge(filter_node_id, view_id, arrowsize='0.7', color='black')

        # Now, connect the initial inputs to the first step in the chain
        for input_node in input_source_nodes:
            cleaned_input = input_node.strip("#")
            
            # If the current view is a JoinView, get the join details for the edge label
            join_label = ""
            if details.get("join_details"):
                join_detail = details["join_details"][0]
                join_type = join_detail["join_type"].replace("outer", "Outer").replace("inner", "Inner").replace("text", "Text")

                label_parts = [f"Type: {join_type}"]

                if join_detail["join_columns"]:
                    # Build condition(s) like "left.col = right.col"
                    conditions = [
                        f"{join_detail['left_table']}.{col} = {join_detail['right_table']}.{col}"
                        for col in join_detail["join_columns"]
                    ]
                    label_parts.append(" AND ".join(conditions))

                join_label = "\n".join(label_parts)

            
            # Determine the target of this specific input edge
            edge_target = view_id
            if has_filter:
                edge_target = f"{view_id}_filter"
            elif has_calc_attrs:
                edge_target = f"{view_id}_calc"

            # Draw the edge with appropriate styling
            g.edge(cleaned_input, edge_target, label=join_label, fontsize='9', arrowsize='0.7', color='black')

    # Add a final edge from the last calculation view to the output node
    if analysis_data["calculation_views"]:
        last_view_id = list(analysis_data["calculation_views"].keys())[-1]
        
        # Check if the last view has a filter or calc attr, and if so,
        # point the final arrow from the last intermediary node.
        last_view_details = analysis_data["calculation_views"][last_view_id]
        last_source = last_view_id
        if last_view_details.get("calculated_attributes"):
            last_source = f"{last_view_id}_calc"
        elif last_view_details.get("filters"):
            last_source = f"{last_view_id}_filter"
            
        g.edge(last_source, output_node_id, arrowsize='0.7', color='black')
        
    return g.source
