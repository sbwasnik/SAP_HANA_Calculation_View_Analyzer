# app.py
# This is the main Streamlit application file. It handles the UI,
# file uploading, and calls the functions to analyze and visualize the XML.

import streamlit as st # type: ignore
import xml.etree.ElementTree as ET
from function import analyze_cv, generate_graphviz_dot
import graphviz 

# Set the page configuration to use a wide layout for better visualization
st.set_page_config(layout="wide")

st.title("SAP HANA Calculation View Analyzer")
with st.sidebar:
    st.markdown(
        "Upload a `.calculationview` XML file to get a detailed breakdown of its structure, data sources, and logic."
    )

    # File uploader widget for the user to upload a .calculationview file
    uploaded_file = st.file_uploader(
        "Choose a .calculationview file", type=["calculationview", "xml"]
    )

# Check if a file has been uploaded
if uploaded_file is not None:
    try:
        # Read the file content as a string
        xml_content = uploaded_file.getvalue().decode("utf-8")

        # Parse and analyze the XML content using the function from function.py
        analysis_result = analyze_cv(xml_content)

        # Generate the detailed DOT string for the graph
        # This function now includes join details on the edges
        dot_string = generate_graphviz_dot(analysis_result)

        # Display the analysis results in a structured way using Streamlit expanders
        st.header("Analysis Report")
        st.write("---")

        # Expander for General Information
        with st.expander("General Information", expanded=False):
            st.markdown(f"**ID:** `{analysis_result['general']['id']}`")
            st.markdown(f"**Type:** `{analysis_result['general']['type']}`")
            st.markdown(f"**Visibility:** `{analysis_result['general']['visibility']}`")
            st.markdown(f"**Calculation Scenario Type:** `{analysis_result['general']['calculationScenarioType']}`")
            st.markdown(f"**Output View Type:** `{analysis_result['general']['outputViewType']}`")
            st.markdown(f"**Last Changed:** `{analysis_result['general']['changedAt']}`")
        

                # Expander for the final output model
        with st.expander("Final Output (Logical Model)", expanded=False):
            st.subheader("Dimensions:")
            st.dataframe(
                analysis_result["final_output"]["attributes"],
                use_container_width=True,
                hide_index=True
            )
            if not analysis_result["final_output"]["measures"].empty:
                st.subheader("Measures:")
                st.dataframe(
                    analysis_result["final_output"]["measures"],
                    use_container_width=True,
                    hide_index=True
                )
         
     

        # Expander for Data Sources
        with st.expander("Data Sources", expanded=False):
            st.subheader("Tables and Views Used:")
            df = analysis_result["data_sources"]
            df = df.drop(columns=["ID"], errors="ignore")
            st.dataframe(
                df, use_container_width=True, hide_index=True
            )

        # Expander for a breakdown of each Calculation View
        # with st.expander("Calculation Views and Data Flow", expanded=False):
        #     st.subheader("Breakdown of Each Calculation View:")
        #     for view_id, details in analysis_result["calculation_views"].items():
        #         with st.container(border=True):
        #             st.markdown(f"#### ID: `{view_id}`")
        #             st.markdown(f"**Type:** `{details['type']}`")
        #             if details["inputs"]:
        #                 st.markdown("**Inputs:**")
        #                 for input_node in details["inputs"]:
        #                     st.markdown(f"- `{input_node}`")

        #             if details.get("filters"):
        #                 st.markdown("**Filters:**")
        #                 st.code(details["filters"])

        #             if details.get("join_attributes"):
        #                 st.markdown("**Join Attributes:**")
        #                 st.markdown(f"`{', '.join(details['join_attributes'])}`")
                    
        #             if details.get("join_details"):
        #                 st.markdown("**Join Details:**")
        #                 for detail in details["join_details"]:
        #                     st.markdown(f"- **Join Type:** `{detail['join_type']}`")
        #                     st.markdown(f"  **Left Table:** `{detail['left_table']}`")
        #                     st.markdown(f"  **Right Table:** `{detail['right_table']}`")
        #                     st.markdown(f"  **joinAttribute:** `{detail['joinAttribute']}`")


        #             if details.get("calculated_attributes"):
        #                 st.markdown("**Calculated Attributes:**")
        #                 for calc_attr in details["calculated_attributes"]:
        #                     st.markdown(
        #                         f"- **{calc_attr['id']}** ({calc_attr['datatype']}):"
        #                     )
        #                     st.code(calc_attr["formula"])
        
        # Expander for calculated columns
        with st.expander("Calculated Attributes", expanded=False):
        
            for view_id, details in analysis_result["calculation_views"].items():
                if details.get("calculated_attributes"):
                    
                    for calc_attr in details["calculated_attributes"]:
                        with st.container(border=True):
                            st.write(f"Attribute Name: **{calc_attr['id']}** ")
                            st.write(f"Attribute Datatype: **{calc_attr['datatype']}**")
                            st.write("**Formula:**")
                            st.code(calc_attr["formula"])
                            
                            
        # Expander for filters
        with st.expander("Filters", expanded=False):
            for view_id, details in analysis_result["calculation_views"].items():
                if details.get("filters"):
                    with st.container(border=True):
                        st.write(f"Filter on Calculation View: **{view_id}** ")
                        st.write("**Filter Expression:**")
                        st.code(details["filters"])


        # Expander for joins
        with st.expander("Join Details", expanded=False):
            for view_id, details in analysis_result["calculation_views"].items():
                if details.get("join_details"):
                    
                    for join_detail in details["join_details"]:
                        with st.container(border=True):
                            st.write(f"Join on Calculation View: **{view_id}** ")
                            st.write(f"**Join Type:** `{join_detail['join_type']}`")
                            st.write(f"**Left Table:** `{join_detail['left_table']}`")
                            st.write(f"**Right Table:** `{join_detail['right_table']}`")
                            st.write(f"**Join Attribute:** `{join_detail['joinAttribute']}`")
                            st.write(f"**Join Columns:** `{', '.join(join_detail['join_columns'])}`")
        
        



        # Expander for the detailed Data Flow Graph
        with st.expander("Data Flow Graph", expanded=True):
            st.markdown("### Detailed Graph of Data Flow and Joins")
            st.graphviz_chart(dot_string)
            
            # Convert DOT string to a Graphviz object
            graph = graphviz.Source(dot_string)

            # Export the graph as PNG (you can also use "svg" or "pdf")
            graph_bytes = graph.pipe(format="png")

            # Download button
            st.download_button(
                label="📥 Download Graph as PNG",
                data=graph_bytes,
                file_name=f"{analysis_result['general']['id']}_data_flow.png",
                mime="image/png"
            )
        
        



            
            
    except ET.ParseError as e:
        # Handle XML parsing errors gracefully
        st.error(f"Error parsing XML file: {e}")
        st.write(
            "Please ensure the uploaded file is a valid `.calculationview` XML."
        )
    except Exception as e:
        # Handle any other unexpected errors
        st.error(f"An unexpected error occurred: {e}")
