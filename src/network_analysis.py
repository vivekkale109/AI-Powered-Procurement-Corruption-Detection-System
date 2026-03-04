"""
Network Analysis Module.
Constructs and analyzes network of contractor relationships and bid rotation patterns.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
import networkx as nx
from .utils import Logger

logger = Logger(__name__)


class ContractorNetworkBuilder:
    """Builds network of contractor co-participation relationships."""
    
    def __init__(self, temporal_window_days: int = 730):
        """
        Initialize network builder.
        
        Args:
            temporal_window_days: Time window for co-participation analysis
        """
        self.temporal_window_days = temporal_window_days
        self.graph = None
        self.co_participation_matrix = None
    
    def build_network(self, df: pd.DataFrame) -> nx.Graph:
        """
        Build network of contractor co-participation.
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            NetworkX undirected graph
        """
        logger.info("Building contractor network...")
        
        self.graph = nx.Graph()
        co_participation = defaultdict(int)
        contractor_tenders = defaultdict(set)
        
        # Add edges for co-participation
        for _, row in df.iterrows():
            if 'bidders_normalized' in df.columns:
                bidders = row['bidders_normalized']
            else:
                bidders = [row['winning_bidder_normalized']]
            
            bidders = [b for b in bidders if pd.notna(b) and b != '']
            
            # Record tender participation
            for bidder in bidders:
                contractor_tenders[bidder].add(row['tender_id'])
            
            # Add edges between all pairs
            for i in range(len(bidders)):
                for j in range(i + 1, len(bidders)):
                    bidder1, bidder2 = bidders[i], bidders[j]
                    pair = tuple(sorted([bidder1, bidder2]))
                    co_participation[pair] += 1
        
        # Add nodes
        for bidder in contractor_tenders.keys():
            self.graph.add_node(bidder, tender_count=len(contractor_tenders[bidder]))
        
        # Add weighted edges
        for (bidder1, bidder2), count in co_participation.items():
            if count >= 2:  # Minimum threshold
                self.graph.add_edge(bidder1, bidder2, weight=count)
        
        logger.info(f"Network built: {self.graph.number_of_nodes()} nodes, "
                   f"{self.graph.number_of_edges()} edges")
        
        return self.graph
    
    def get_network_statistics(self) -> Dict:
        """Get network statistics."""
        if self.graph is None:
            return {}
        
        return {
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'avg_degree': np.mean([d for n, d in self.graph.degree()]),
            'num_triangles': sum(nx.triangles(self.graph).values()) // 3,
            'avg_clustering': nx.average_clustering(self.graph)
        }


class SuspiciousClusterDetector:
    """Detects suspicious clusters and communities in network."""
    
    def __init__(self, min_cluster_size: int = 3):
        """
        Initialize detector.
        
        Args:
            min_cluster_size: Minimum nodes in a suspicious cluster
        """
        self.min_cluster_size = min_cluster_size
        self.communities = []
        self.suspicion_scores = {}
    
    def detect_communities(self, graph: nx.Graph) -> List[Set[str]]:
        """
        Detect communities using Louvain algorithm.
        
        Args:
            graph: NetworkX graph
        
        Returns:
            List of communities (sets of nodes)
        """
        logger.info("Detecting communities...")
        
        try:
            from networkx.algorithms import community
            
            # Use greedy modularity optimization
            communities = list(community.greedy_modularity_communities(graph))
            self.communities = communities
            
            logger.info(f"Detected {len(communities)} communities")
            
            return communities
        except Exception as e:
            logger.warning(f"Community detection failed: {e}")
            return []
    
    def score_community_suspicion(self, graph: nx.Graph, community: Set[str]) -> float:
        """
        Score suspicious of a community based on network properties.
        
        Args:
            graph: NetworkX graph
            community: Set of contractor nodes
        
        Returns:
            Suspicion score (0-1)
        """
        if len(community) < self.min_cluster_size:
            return 0
        
        subgraph = graph.subgraph(community).copy()
        
        # Calculate various metrics
        density = nx.density(subgraph)
        
        # High density = tight cluster (suspicious)
        density_score = density
        
        # Clustering coefficient
        avg_clustering = nx.average_clustering(subgraph)
        clustering_score = avg_clustering
        
        # Count triangles (3-way rotation patterns)
        triangles = sum(nx.triangles(subgraph).values()) // 3
        max_triangles = len(community) * (len(community) - 1) * (len(community) - 2) // 6
        triangle_score = triangles / max_triangles if max_triangles > 0 else 0
        
        # Combined suspicion score
        suspicion = np.mean([density_score, clustering_score * 0.8, triangle_score * 0.6])
        
        return min(suspicion, 1.0)
    
    def get_suspicious_clusters(self, graph: nx.Graph, threshold: float = 0.5) -> Dict[int, Dict]:
        """
        Get list of suspicious clusters above threshold.
        
        Args:
            graph: NetworkX graph
            threshold: Suspicion score threshold
        
        Returns:
            Dictionary of cluster_id -> cluster info
        """
        if not self.communities:
            self.detect_communities(graph)
        
        suspicious_clusters = {}
        
        for i, community in enumerate(self.communities):
            suspicion_score = self.score_community_suspicion(graph, community)
            
            if suspicion_score >= threshold:
                suspicious_clusters[i] = {
                    'members': list(community),
                    'size': len(community),
                    'suspicion_score': suspicion_score
                }
        
        return suspicious_clusters


class BidRotationDetector:
    """Detects bid rotation patterns (rotational collusion)."""
    
    def __init__(self):
        """Initialize detector."""
        pass
    
    def detect_rotation_patterns(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Detect bid rotation patterns by analyzing winner sequences.
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            Dictionary of contractor -> rotation metrics
        """
        df = df.sort_values('tender_date')
        
        rotation_metrics = defaultdict(lambda: {
            'wins': [],
            'rotation_score': 0,
            'sequence_regularity': 0,
            'interval_variance': 0
        })
        
        # Group by department/location to find rotation patterns
        for group_key in ['department', 'location']:
            if group_key not in df.columns:
                continue
            
            for group_name, group_df in df.groupby(group_key):
                group_df = group_df.sort_values('tender_date')
                
                # Get sequence of winners
                winners = group_df['winning_bidder_normalized'].tolist()
                
                # Analyze rotation
                rotation_score = self._analyze_winner_rotation(winners)
                
                # Update metrics for each contractor
                for i, winner in enumerate(winners):
                    rotation_metrics[winner]['wins'].append({
                        'position': i,
                        'date': group_df.iloc[i]['tender_date'],
                        'group': group_name,
                        'group_type': group_key
                    })
        
        # Compute rotation scores
        for contractor, metrics in rotation_metrics.items():
            if len(metrics['wins']) > 2:
                intervals = []
                for i in range(len(metrics['wins']) - 1):
                    delta = (metrics['wins'][i + 1]['date'] - metrics['wins'][i]['date']).days
                    intervals.append(delta)
                
                if intervals:
                    metrics['interval_variance'] = np.var(intervals)
                    metrics['sequence_regularity'] = 1 / (1 + metrics['interval_variance'])
                    
                    # Rotation score: how predictable are the wins?
                    # Low variance = high regularity = suspicious rotation
                    metrics['rotation_score'] = metrics['sequence_regularity']
        
        return dict(rotation_metrics)
    
    def _analyze_winner_rotation(self, winners: List[str]) -> float:
        """
        Analyze winner sequence for rotation pattern.
        
        Args:
            winners: List of winning contractor names
        
        Returns:
            Rotation score (0-1)
        """
        if len(winners) < 3:
            return 0
        
        # Count transitions
        transitions = defaultdict(int)
        for i in range(len(winners) - 1):
            pair = (winners[i], winners[i + 1])
            transitions[pair] += 1
        
        # If each transition is unique, could be rotation
        unique_transitions = len(transitions)
        total_transitions = len(winners) - 1
        
        # Rotation score: diversity in transitions
        rotation_score = unique_transitions / total_transitions
        
        # But if too diverse, not actually rotation
        if rotation_score > 0.8:
            return 0
        
        # Otherwise, return how structured it is
        return 1 - rotation_score


class CentralityAnalyzer:
    """Analyzes network centrality measures."""
    
    @staticmethod
    def compute_centrality_measures(graph: nx.Graph) -> Dict[str, Dict[str, float]]:
        """
        Compute various centrality measures for nodes.
        
        Args:
            graph: NetworkX graph
        
        Returns:
            Dictionary of centrality measures
        """
        logger.info("Computing centrality measures...")
        
        centrality_measures = {}
        
        # Degree centrality
        degree_centrality = nx.degree_centrality(graph)
        
        # Betweenness centrality
        betweenness_centrality = nx.betweenness_centrality(graph, weight='weight')
        
        # Closeness centrality
        if nx.is_connected(graph):
            closeness_centrality = nx.closeness_centrality(graph)
        else:
            # For disconnected graphs, compute for each component
            closeness_centrality = {}
            for node in graph.nodes():
                closeness_centrality[node] = 0
            
            for component in nx.connected_components(graph):
                subgraph = graph.subgraph(component)
                component_closeness = nx.closeness_centrality(subgraph)
                closeness_centrality.update(component_closeness)
        
        # Eigenvector centrality (for connected components)
        eigenvector_centrality = {}
        for component in nx.connected_components(graph):
            subgraph = graph.subgraph(component)
            if len(component) > 1:
                try:
                    component_eigen = nx.eigenvector_centrality(subgraph, max_iter=100)
                    eigenvector_centrality.update(component_eigen)
                except:
                    for node in component:
                        eigenvector_centrality[node] = 0
            else:
                eigenvector_centrality[list(component)[0]] = 0
        
        # Combine measures
        for node in graph.nodes():
            centrality_measures[node] = {
                'degree': degree_centrality.get(node, 0),
                'betweenness': betweenness_centrality.get(node, 0),
                'closeness': closeness_centrality.get(node, 0),
                'eigenvector': eigenvector_centrality.get(node, 0)
            }
        
        return centrality_measures


class NetworkAnalyzer:
    """Orchestrates network analysis."""
    
    def __init__(self, temporal_window_days: int = 730):
        """Initialize analyzer."""
        self.builder = ContractorNetworkBuilder(temporal_window_days)
        self.cluster_detector = SuspiciousClusterDetector()
        self.rotation_detector = BidRotationDetector()
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Perform comprehensive network analysis.
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            Dictionary with analysis results
        """
        logger.info("Starting network analysis...")
        
        # Build network
        graph = self.builder.build_network(df)
        
        # Get network stats
        network_stats = self.builder.get_network_statistics()
        
        # Detect communities
        communities = self.cluster_detector.detect_communities(graph)
        suspicious_clusters = self.cluster_detector.get_suspicious_clusters(graph, threshold=0.4)
        
        # Detect rotation patterns
        rotation_patterns = self.rotation_detector.detect_rotation_patterns(df)
        
        # Compute centrality
        centrality = CentralityAnalyzer.compute_centrality_measures(graph)
        
        logger.info("Network analysis completed")
        
        return {
            'graph': graph,
            'network_stats': network_stats,
            'communities': communities,
            'suspicious_clusters': suspicious_clusters,
            'rotation_patterns': rotation_patterns,
            'centrality': centrality
        }
