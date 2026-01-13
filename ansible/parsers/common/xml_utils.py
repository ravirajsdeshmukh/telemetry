#!/usr/bin/env python3
"""
Common XML parsing utilities for all vendors.
Provides namespace-agnostic XML element access.
"""

from typing import Optional, List
import xml.etree.ElementTree as ET


def strip_namespace(tag: str) -> str:
    """
    Remove namespace from XML tag.
    
    Args:
        tag: XML tag with or without namespace
        
    Returns:
        Tag without namespace
        
    Example:
        >>> strip_namespace('{http://xml.juniper.net/junos/22.1R1/junos}interface-information')
        'interface-information'
    """
    return tag.split('}', 1)[1] if '}' in tag else tag


def findtext_ns(element: ET.Element, tag: str, default: Optional[str] = None) -> Optional[str]:
    """
    Find text of child element with tag, ignoring namespace.
    
    Args:
        element: Parent XML element
        tag: Tag name to search for (without namespace)
        default: Default value if not found
        
    Returns:
        Text content of matching element or default
    """
    if element is None:
        return default
    
    for child in element:
        if strip_namespace(child.tag) == tag:
            return child.text if child.text else default
    return default


def find_ns(element: ET.Element, tag: str) -> Optional[ET.Element]:
    """
    Find first child element with tag, ignoring namespace.
    
    Args:
        element: Parent XML element
        tag: Tag name to search for (without namespace)
        
    Returns:
        Matching element or None
    """
    if element is None:
        return None
    
    for child in element:
        if strip_namespace(child.tag) == tag:
            return child
    return None


def findall_ns(element: ET.Element, tag: str) -> List[ET.Element]:
    """
    Find all child elements with tag, ignoring namespace.
    
    Args:
        element: Parent XML element
        tag: Tag name to search for (without namespace)
        
    Returns:
        List of matching elements
    """
    if element is None:
        return []
    
    return [child for child in element if strip_namespace(child.tag) == tag]


def findall_recursive_ns(element: ET.Element, tag: str) -> List[ET.Element]:
    """
    Find all descendant elements with tag, ignoring namespace.
    Searches recursively through all levels.
    
    Args:
        element: Parent XML element
        tag: Tag name to search for (without namespace)
        
    Returns:
        List of matching elements from all levels
    """
    if element is None:
        return []
    
    results = []
    for child in element.iter():
        if strip_namespace(child.tag) == tag:
            results.append(child)
    return results


def extract_numeric_value(text: Optional[str], default: Optional[float] = None) -> Optional[float]:
    """
    Extract numeric value from text, handling various formats.
    
    Args:
        text: Text containing numeric value (may include units)
        default: Default value if extraction fails
        
    Returns:
        Numeric value or default
        
    Example:
        >>> extract_numeric_value("3.25 V")
        3.25
        >>> extract_numeric_value("-2.5 dBm")
        -2.5
    """
    if not text:
        return default
    
    try:
        # Remove common units and extract numeric part
        cleaned = text.strip().split()[0]
        return float(cleaned)
    except (ValueError, IndexError):
        return default
