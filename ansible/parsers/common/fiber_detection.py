#!/usr/bin/env python3
"""
Fiber type detection logic - vendor agnostic.
Determines Single-Mode vs Multi-Mode fiber based on media type, wavelength, or description.
"""

from typing import Optional


def determine_fiber_type(
    media_type: Optional[str] = None,
    description: Optional[str] = None,
    wavelength_nm: Optional[int] = None
) -> Optional[str]:
    """
    Determine fiber type based on available information.
    
    Args:
        media_type: Media type string (e.g., "100GBASE-SR4", "10GBASE-LR")
        description: Description string from device inventory
        wavelength_nm: Wavelength in nanometers
    
    Returns:
        "FIBER_TYPE_SINGLE_MODE" or "FIBER_TYPE_MULTI_MODE" or None
        
    Examples:
        >>> determine_fiber_type(media_type="100GBASE-SR4")
        'FIBER_TYPE_MULTI_MODE'
        >>> determine_fiber_type(media_type="10GBASE-LR")
        'FIBER_TYPE_SINGLE_MODE'
        >>> determine_fiber_type(wavelength_nm=850)
        'FIBER_TYPE_MULTI_MODE'
        >>> determine_fiber_type(wavelength_nm=1310)
        'FIBER_TYPE_SINGLE_MODE'
    """
    # Method 1: Wavelength-based detection (most reliable)
    if wavelength_nm:
        if wavelength_nm == 850:
            return "FIBER_TYPE_MULTI_MODE"
        elif wavelength_nm in [1310, 1550]:
            return "FIBER_TYPE_SINGLE_MODE"
        # CWDM/DWDM wavelengths (1270-1610nm range)
        elif 1270 <= wavelength_nm <= 1610:
            return "FIBER_TYPE_SINGLE_MODE"
    
    # Method 2: Media type pattern matching
    if media_type:
        media_upper = media_type.upper().replace('-', '').replace(' ', '')
        
        # Multi-mode indicators
        mmf_patterns = [
            'SR',      # Short Reach (850nm, MMF)
            'SX',      # Short Wavelength (850nm, MMF)
            'VCSEL',   # Vertical Cavity Surface Emitting Laser (typically 850nm, MMF)
            '850NM',
            'MMF',
            'MULTIMODE'
        ]
        if any(pattern in media_upper for pattern in mmf_patterns):
            return "FIBER_TYPE_MULTI_MODE"
        
        # Single-mode indicators
        smf_patterns = [
            'LR',      # Long Reach (1310nm, SMF)
            'ER',      # Extended Reach (1550nm, SMF)
            'ZR',      # Ultra Long Reach (1550nm, SMF)
            'LX',      # Long Wavelength (1310nm, SMF)
            'EX',      # Extended (typically SMF)
            'ZX',      # Extended Extended (typically SMF)
            '1310NM',
            '1550NM',
            'CWDM',    # Coarse WDM (SMF)
            'DWDM',    # Dense WDM (SMF)
            'SMF',
            'SINGLEMODE'
        ]
        if any(pattern in media_upper for pattern in smf_patterns):
            return "FIBER_TYPE_SINGLE_MODE"
    
    # Method 3: Description pattern matching (fallback)
    if description:
        desc_upper = description.upper().replace('-', '').replace(' ', '')
        
        # Multi-mode indicators
        mmf_patterns = ['SR', 'SX', 'VCSEL', '850NM', 'MMF', 'MULTIMODE', 'SHORT']
        if any(pattern in desc_upper for pattern in mmf_patterns):
            return "FIBER_TYPE_MULTI_MODE"
        
        # Single-mode indicators
        smf_patterns = [
            'LR', 'ER', 'ZR', 'LX', 'EX', 'ZX',
            '1310NM', '1550NM', 'CWDM', 'DWDM',
            'SMF', 'SINGLEMODE', 'LONG', 'EXTENDED'
        ]
        if any(pattern in desc_upper for pattern in smf_patterns):
            return "FIBER_TYPE_SINGLE_MODE"
    
    return None


# Fiber type constants
FIBER_TYPE_SINGLE_MODE = "FIBER_TYPE_SINGLE_MODE"
FIBER_TYPE_MULTI_MODE = "FIBER_TYPE_MULTI_MODE"
