#!/usr/bin/env python3
"""
Interface naming conventions and FPC/PIC/Port mapping logic.
Maps chassis hardware locations to interface names across different vendors and platforms.
"""

from typing import Optional, Dict
import re


# Platform-specific interface prefix mappings
JUNIPER_PREFIX_MAP = {
    # QFX Series
    'qfx5240': 'et',
    'qfx5230': 'et',
    'qfx5220': 'et',
    'qfx5210': 'et',
    'qfx5200': 'et',
    'qfx5130': 'et',
    'qfx5120': 'et',
    'qfx5110': 'xe',
    'qfx5100': 'xe',
    'qfx10k': 'et',
    # MX Series
    'mx': 'et',
    'mx960': 'et',
    'mx480': 'et',
    'mx240': 'et',
    'mx204': 'et',
    'mx150': 'et',
    # PTX Series
    'ptx': 'et',
    'ptx10k': 'et',
    'ptx5000': 'et',
    'ptx3000': 'et',
    'ptx1000': 'et',
    # EX Series (typically xe for 10G)
    'ex': 'xe',
    'ex4300': 'ge',
    'ex4600': 'et',
}


def parse_juniper_interface_name(
    fpc: str,
    pic: str,
    port: str,
    platform_hint: Optional[str] = None
) -> Optional[str]:
    """
    Map Juniper FPC/PIC/Port to interface name.
    
    Args:
        fpc: FPC (Flexible PIC Concentrator) number
        pic: PIC (Physical Interface Card) number
        port: Port/Xcvr number
        platform_hint: Optional platform identifier (e.g., "qfx5240", "mx960")
    
    Returns:
        Interface name (e.g., "et-0/0/6") or None
        
    Examples:
        >>> parse_juniper_interface_name("0", "0", "6", "qfx5240")
        'et-0/0/6'
        >>> parse_juniper_interface_name("1", "2", "3", "mx960")
        'et-1/2/3'
    """
    # Determine interface prefix based on platform
    prefix = 'et'  # default for modern platforms
    
    if platform_hint:
        platform_lower = platform_hint.lower()
        for key, val in JUNIPER_PREFIX_MAP.items():
            if key in platform_lower:
                prefix = val
                break
    
    # Standard Juniper format: {prefix}-{fpc}/{pic}/{port}
    return f"{prefix}-{fpc}/{pic}/{port}"


def extract_fpc_pic_port(module_name: str) -> Optional[Dict[str, str]]:
    """
    Extract FPC, PIC, and Port numbers from module names.
    
    Args:
        module_name: Module name (e.g., "FPC 0", "PIC 1", "Xcvr 6")
    
    Returns:
        Dictionary with extracted numbers or None
        
    Examples:
        >>> extract_fpc_pic_port("FPC 0")
        {'type': 'fpc', 'number': '0'}
        >>> extract_fpc_pic_port("Xcvr 32")
        {'type': 'port', 'number': '32'}
    """
    # Match FPC
    fpc_match = re.search(r'FPC\s+(\d+)', module_name, re.IGNORECASE)
    if fpc_match:
        return {'type': 'fpc', 'number': fpc_match.group(1)}
    
    # Match PIC
    pic_match = re.search(r'PIC\s+(\d+)', module_name, re.IGNORECASE)
    if pic_match:
        return {'type': 'pic', 'number': pic_match.group(1)}
    
    # Match Xcvr (transceiver/port)
    xcvr_match = re.search(r'Xcvr\s+(\d+)', module_name, re.IGNORECASE)
    if xcvr_match:
        return {'type': 'port', 'number': xcvr_match.group(1)}
    
    return None


def parse_interface_base_name(interface_name: str) -> str:
    """
    Extract base interface name without channel suffix.
    Normalizes interface prefix to 'et-' for consistent matching with chassis inventory.
    
    Args:
        interface_name: Full interface name (e.g., "et-0/0/6:2", "xe-0/0/6")
    
    Returns:
        Base interface name normalized to 'et-' prefix (e.g., "et-0/0/6")
        
    Examples:
        >>> parse_interface_base_name("et-0/0/6:2")
        'et-0/0/6'
        >>> parse_interface_base_name("xe-0/0/48")
        'et-0/0/48'
    """
    # Remove channelized interface suffix (:N)
    base_name = interface_name.split(':')[0] if ':' in interface_name else interface_name
    
    # Normalize xe- prefix to et- for consistent matching with chassis inventory
    # The chassis inventory always uses et- prefix, but optics diagnostics may use xe-
    if base_name.startswith('xe-'):
        base_name = 'et-' + base_name[3:]
    
    return base_name


def get_interface_channel(interface_name: str) -> Optional[int]:
    """
    Extract channel number from channelized interface name.
    
    Args:
        interface_name: Full interface name (e.g., "et-0/0/6:2")
    
    Returns:
        Channel number or None if not channelized
        
    Examples:
        >>> get_interface_channel("et-0/0/6:2")
        2
        >>> get_interface_channel("xe-0/0/48")
        None
    """
    if ':' in interface_name:
        try:
            return int(interface_name.split(':')[1])
        except (ValueError, IndexError):
            return None
    return None
