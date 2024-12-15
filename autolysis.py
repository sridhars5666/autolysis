from io import StringIO
import os
import sys
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import requests
import math
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

# Configuration
AIPROXY_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIzZjEwMDAxNzhAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.yOrJJxuhOmCtLdpcOHX51no76oIcGxvEdlZYlTrDBKQ"
API_BASE_URL = "http://aiproxy.sanand.workers.dev/openai/v1"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {AIPROXY_TOKEN}"
}

def read_csv(file_name):
    try:
        df = pd.read_csv(file_name)
        return df
    except Exception as e:
        print(f"Error reading file {file_name}: {e}")
        sys.exit(1)

def create_output_directory(file_name):
    # Create a directory with the base name of the file
    file_name = file_name.strip(".csv")
    output_dir = f"./{file_name}"
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    
    return output_dir

# Function to handle missing values and generate missing_values.png
def null_value(df, output_dir):
    # Missing values bar plot
    missing = df.isnull().sum()
    missing_percentage = (missing / df.shape[0]) * 100  # Convert count to percentage
    if missing.any():
        plt.figure(figsize=(8, 6))
        missing_percentage.plot(kind="bar", color="skyblue")
        plt.title("Missing Values by Column (Percentage)")
        plt.ylabel("Percentage")
        plt.savefig(os.path.join(output_dir, "missing_values.png"), bbox_inches='tight')  # Save directly to file
        plt.close()
    
    return missing

def detect_outliers(df, threshold=1.5):
    """Detect outliers using z-score method and return as a DataFrame."""
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    outlier_data = []

    for col in numeric_columns:
        col_mean = np.mean(df[col])
        col_std = np.std(df[col])
        z_scores = (df[col] - col_mean) / col_std

        # Find outlier indices
        outlier_indices = np.where(np.abs(z_scores) > threshold)[0]

        # Append outlier information
        for idx in outlier_indices:
            outlier_data.append({
                "Column": col,
                "Index": idx,
                "Value": df[col].iloc[idx],
                "Z-Score": z_scores[idx]
            })

    # Convert to DataFrame
    outliers_df = pd.DataFrame(outlier_data)
    return outliers_df

def visualize_outliers(df, outliers_df, output_dir):
    """Visualize data and highlight outliers using box plots."""
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    
    # Check if numeric columns are present
    if numeric_columns.empty:
        return

    num_cols = 4  # Number of columns in the subplot grid
    num_rows = math.ceil(len(numeric_columns) / num_cols)  # Dynamically calculate rows
    
    # Set up the figure size dynamically based on the number of columns
    plt.figure(figsize=(num_cols * 5, num_rows * 5), dpi=100)
    
    for i, col in enumerate(numeric_columns, 1):
        plt.subplot(num_rows, num_cols, i)  # Create subplot grid
        sns.boxplot(x=df[col], color="skyblue", flierprops={"marker": "o", "color": "red"})
        plt.title(f"Boxplot for {col}")
        
        # Highlight outliers if present
        col_outliers = outliers_df[outliers_df["Column"] == col]
        if not col_outliers.empty:
            for value in col_outliers["Value"]:
                plt.plot(1, value, 'ro')  # Plot red dots for outliers

    # Save the plot
    try:
        plt.savefig(os.path.join(output_dir, "outlier_visualization.png"), bbox_inches="tight")
        print(f"Saved outlier visualization at: {os.path.abspath('outlier_visualization.png')}")
    except Exception as e:
        print(f"Error saving plot: {e}")
    
    plt.close()
   
def detect_target_column(df):
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    if numeric_columns.any():
        return numeric_columns[-1]  # Assume the last numeric column is the target
    return None

def detect_columns_by_keywords(df, keywords):
    return [col for col in df.columns if any(keyword in col.lower() for keyword in keywords)]

def handle_missing_values(df):
    numeric_imputer = SimpleImputer(strategy="median")
    df[df.select_dtypes(include=[np.number]).columns] = numeric_imputer.fit_transform(
        df.select_dtypes(include=[np.number])
    )

    categorical_imputer = SimpleImputer(strategy="most_frequent")
    df[df.select_dtypes(include=['object']).columns] = categorical_imputer.fit_transform(
        df.select_dtypes(include=['object'])
    )
    return df

def elbow_method(df, output_dir):
    numeric_data = df.select_dtypes(include=[np.number]).fillna(0)
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(numeric_data)

    wcss = []
    max_clusters = min(10, len(scaled_data))  # Adjust max clusters to the number of samples
    for i in range(1, max_clusters + 1):
        kmeans = KMeans(n_clusters=i, random_state=42)
        kmeans.fit(scaled_data)
        wcss.append(kmeans.inertia_)

    plt.figure(figsize=(8, 6))
    plt.plot(range(1, max_clusters + 1), wcss, marker='o', linestyle='--', color='b')
    plt.title("Elbow Method")
    plt.xlabel("Number of Clusters")
    plt.ylabel("WCSS")
    plt.savefig(os.path.join(output_dir, "elbow_method.png"), bbox_inches='tight')
    return wcss

def analyze_data(df, clustering=True, n_clusters=3):
    summary_stats = df.describe(include='all').transpose()
    correlation_matrix = df.select_dtypes(include=['number']).corr()

    clustering_results = {}
    if clustering:
        numeric_data = df.select_dtypes(include=[np.number]).dropna()
        if not numeric_data.empty:
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(numeric_data)
            kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(scaled_data)
            hierarchical_linkage = linkage(scaled_data, method='ward')

            clustering_results = {
                "kmeans_labels": pd.Series(kmeans.labels_, index=numeric_data.index),
                "hierarchical_linkage": hierarchical_linkage
            }

    results = {
        "summary_statistics": summary_stats,
        "correlation_matrix": correlation_matrix,
        "clustering_results": clustering_results
    }

    return results

def visualize_data(df, analysis_results, output_dir):
    correlation_matrix = analysis_results['correlation_matrix']
    clustering_results = analysis_results['clustering_results']

    if not correlation_matrix.empty:
        plt.figure(figsize=(8, 6))
        sns.heatmap(correlation_matrix, annot=True, cmap="coolwarm")
        plt.title("Correlation Matrix")
        plt.savefig(os.path.join(output_dir, "correlation_heatmap.png"), bbox_inches='tight')

    if clustering_results:
        df['Cluster'] = clustering_results['kmeans_labels'].reindex(df.index)
        sns.pairplot(df, hue='Cluster', diag_kind='kde')
        plt.title("KMeans Clustering Visualization")
        plt.savefig(os.path.join(output_dir, "kmeans_clustering.png"), bbox_inches='tight')

        plt.figure(figsize=(10, 6))
        dendrogram(clustering_results['hierarchical_linkage'])
        plt.title("Hierarchical Clustering Dendrogram")
        plt.xlabel("Samples")
        plt.ylabel("Distance")
        plt.savefig(os.path.join(output_dir, "hierarchical_dendrogram.png"), bbox_inches='tight')

def generate_readme(data_summary, chart_files, generated_code_outputs, narrative, output_dir):
    """
    Generate a README file summarizing the analysis and linking visualizations.

    Parameters:
        data_summary (dict): Summary of data analysis.
        chart_files (list): List of file paths to saved charts.
        narrative (str): Narrative description of the analysis.
    """
    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as readme:
        readme.write("# Data Analysis Report\n\n")

        # Summary Statistics
        readme.write("## Summary Statistics\n")
        if 'summary_statistics' in data_summary:
            readme.write(data_summary['summary_statistics'].to_string())
        else:
            readme.write("No summary statistics available.\n")

        # Missing Values
        readme.write("\n\n## Missing Values\n")
        if 'missing_values' in data_summary:
            readme.write(data_summary['missing_values'].to_string())
        else:
            readme.write("No missing values information available.\n")

        # Outliers
        readme.write("\n\n## Outliers\n")
        if 'outliers' in data_summary:
            readme.write(data_summary['outliers'].to_string())
        else:
            readme.write("No outliers detected.\n")

        # Correlation Matrix
        readme.write("\n\n## Correlation Matrix\n")
        if 'correlation_matrix' in data_summary:
            readme.write(data_summary['correlation_matrix'].to_string())
        else:
            readme.write("No correlation matrix available.\n")

        # Clustering Analysis
        readme.write("\n\n## Clustering Analysis\n")
        if 'clustering_results' in data_summary and data_summary['clustering_results']:
            kmeans_labels = data_summary['clustering_results']['kmeans_labels']
            readme.write("### KMeans Clustering\n")
            readme.write(f"Unique clusters: {set(kmeans_labels)}\n")
        else:
            readme.write("No clustering analysis performed.\n")

        # Visualizations
        readme.write("\n\n## Visualizations\n")
        for chart in chart_files:
            if os.path.exists(chart):  # Check if chart file exists
                readme.write(f"![Visualization: {os.path.basename(chart)}]({chart})\n")
            else:
                print(f"Warning: File {chart} not found. Skipping.")

        # Generated Code's output
        readme.write("\n\n## AI Generated Code\n")
        readme.write(generated_code_outputs[0])

        readme.write("\n\n## AI Generated Code's Output\n")
        readme.write(generated_code_outputs[1])

        # Narrative Summary
        readme.write("\n\n## Narrative Summary\n")
        readme.write(narrative)

def generate_narrative(data_summary, api_analysis):
    """
    Generate a narrative summary of the analysis results.

    Parameters:
        data_summary (dict): Summary of data analysis.
        api_analysis (str): Analysis generated by the AI API.

    Returns:
        str: Narrative description of the analysis.
    """
    narrative = []

    # Introduction
    narrative.append("Our analysis journey began by exploring a dataset with rich insights.")

    # Missing values
    missing_values = data_summary.get("missing_values", None)
    if missing_values is not None and missing_values.any():
        narrative.append(f"One of the first challenges was handling missing values. "
                         f"We identified missing data in the following columns: {', '.join(missing_values[missing_values > 0].index.tolist())}.")
    else:
        narrative.append("The dataset had no missing values, making the analysis smoother.")
    
    # Outliers detection
    outliers_df = data_summary.get("outliers", None)
    if outliers_df is not None and not outliers_df.empty:
        outlier_columns = outliers_df["Column"].unique()
        narrative.append(
            f"The next challenge was handling outlier values. "
            f"Outliers were identified in the following columns: {', '.join(outlier_columns)}. "
            f"In total, {len(outliers_df)} outliers were detected across these columns."
        )
    else:
        narrative.append("The dataset had no significant outliers, making it easier to proceed.")

    # Correlation analysis
    correlation_matrix = data_summary.get("correlation_matrix", None)
    if correlation_matrix is not None:
        narrative.append("We examined correlations between numeric variables. "
                         "A heatmap provided insights into how features are interrelated, revealing key associations.")

    # Clustering
    clustering_results = data_summary.get("clustering_results", {})
    if "kmeans_labels" in clustering_results:
        narrative.append(f"KMeans clustering was performed, dividing the data into {len(set(clustering_results['kmeans_labels']))} clusters. "
                         "These clusters were visualized to understand groupings within the dataset.")
    if "hierarchical_linkage" in clustering_results:
        narrative.append("A hierarchical dendrogram further highlighted relationships between data points.")

    # API Analysis Integration
    narrative.append("\n## Insights from AI Analysis\n")
    narrative.append(api_analysis)

    # Conclusion
    narrative.append("This analysis provided actionable insights, paving the way for data-driven decisions.")

    return "\n".join(narrative)

def call_api(endpoint, payload):
    """Generic function to call AI Proxy endpoints using requests."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/{endpoint}",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling AI Proxy: {e}")
        return None
    
def get_generated_code_output(df):
    messages = [
        {"role": "system", "content": "You are an expert Python programmer."},
        {"role": "user", "content": f"Write Python code to analyze the following dataset:\n\nColumns: {df.columns.tolist()}\n\nGenerate code for data cleaning, analysis, and visualizations. The response should have only the code"}
    ]
    payload = {
        "model": "gpt-4o-mini",  # Specify the model
        "messages": messages
    }

    generated_code_response = call_api("chat/completions", payload)
    generated_code = "No code generated."  # Default message if AI fails
    
    if generated_code_response and 'choices' in generated_code_response:
        generated_code = generated_code_response['choices'][0]['message']['content']

    generated_code = generated_code.strip('```python\n').strip('```').strip()
        
    captured_output = StringIO()
    sys.stdout = captured_output

    try:
        exec(generated_code)
    except Exception as e:
        print(f"Error while executing generated code: {e}")          

    sys.stdout = sys.__stdout__
    return [generated_code, captured_output.getvalue()]


def main():
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <dataset.csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} does not exist.")
        sys.exit(1)

    df = read_csv(input_file)
    output_dir = create_output_directory(input_file)

    missing_values = null_value(df, output_dir)

    # Make sure that outliers_df is valid and contains data
    outliers_df = detect_outliers(df)
    if not outliers_df.empty:
        visualize_outliers(df, outliers_df, output_dir)
  
    df = handle_missing_values(df)

    target_column = detect_target_column(df)
    
    date_columns = detect_columns_by_keywords(df, ["date", "time"])

    wcss = elbow_method(df, output_dir)
    
    messages = [
        {"role": "system", "content": "You are an expert data analyst."},
        {"role": "user", "content": f"Analyze the following data:\n\nColumns: {df.columns.tolist()}\n\nProvide insights and patterns."}
    ]

    payload = {
        "model": "gpt-4o-mini",  # Specify model
        "messages": messages
    }

    # Call the API
    api_response = call_api("chat/completions", payload)
    api_analysis = "No insights provided by AI."  # Default message if API fails
    if api_response and 'choices' in api_response:
        api_analysis = api_response['choices'][0]['message']['content']

    analysis_results = analyze_data(df, clustering=True, n_clusters=3)
    analysis_results["missing_values"] = missing_values
    analysis_results["outliers"] = outliers_df
    analysis_results["wcss"]= wcss
    
    narrative = generate_narrative(analysis_results, api_analysis)
    visualize_data(df, analysis_results, output_dir)

    generated_code_response = get_generated_code_output(df)
    
    generate_readme(analysis_results, [
        "correlation_heatmap.png",
        "missing_values.png",
        "outlier_visualization.png",
        "kmeans_clustering.png",
        "hierarchical_dendrogram.png",
        "elbow_method.png"
    ], generated_code_response,
    narrative, output_dir)

    print("\nAnalysis report saved to 'README.md'.")

if __name__ == "__main__":
    main()
