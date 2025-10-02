/**
 * Component for managing brand names and terms for Ground Truth generation.
 */

import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';

interface BrandsTermsManagerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectionsChange?: (selectedBrands: string[], selectedTerms: string[]) => void;
}


export const BrandsTermsManager: React.FC<BrandsTermsManagerProps> = ({ isOpen, onClose, onSelectionsChange }) => {
  // Available items (loaded from database)
  const [availableBrands, setAvailableBrands] = useState<string[]>([]);
  const [availableTerms, setAvailableTerms] = useState<string[]>([]);
  // Selected items (local UI selection state)
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedTerms, setSelectedTerms] = useState<string[]>([]);
  
  const [newBrand, setNewBrand] = useState('');
  const [newTerm, setNewTerm] = useState('');
  const [newTermPronunciation, setNewTermPronunciation] = useState('');
  const [newTermDifficulty, setNewTermDifficulty] = useState<'easy' | 'intermediate' | 'hard'>('intermediate');
  const [loading, setLoading] = useState(false);
  const [deleteMode, setDeleteMode] = useState(false);
  const [activeTab, setActiveTab] = useState<'brands' | 'terms'>('brands');
  const [selectedVertical, setSelectedVertical] = useState<'aesthetic_medicine' | 'dermatology' | 'plastic_surgery' | 'venous_care'>('aesthetic_medicine');
  const [enhancedTerms, setEnhancedTerms] = useState<{[key: string]: {phonetic: string, difficulty: string}}>({});
  const [brandsForDeletion, setBrandsForDeletion] = useState<Set<string>>(new Set());
  const [termsForDeletion, setTermsForDeletion] = useState<Set<string>>(new Set());
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);
  const [deleteType, setDeleteType] = useState<'brands' | 'terms'>('brands');
  const [editingBrand, setEditingBrand] = useState<string | null>(null);
  const [editingTerm, setEditingTerm] = useState<string | null>(null);
  const [editFormData, setEditFormData] = useState<{name: string, phonetic: string, difficulty: string}>({name: '', phonetic: '', difficulty: 'intermediate'});
  const [enhancedBrands, setEnhancedBrands] = useState<{[key: string]: {phonetic: string, difficulty: string}}>({});
  const [operationLoading, setOperationLoading] = useState(false);
  
  // New state for difficulty-based UI improvements
  const [collapsedSections, setCollapsedSections] = useState<{[key: string]: boolean}>({
    easy: false,
    intermediate: false,
    hard: false
  });
  const [difficultySelections, setDifficultySelections] = useState<{[key: string]: string[]}>({
    easy: [],
    intermediate: [],
    hard: []
  });

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen, selectedVertical]);

  useEffect(() => {
    setBrandsForDeletion(new Set());
    setTermsForDeletion(new Set());
  }, [selectedVertical]);

  // Notify parent component when selections change
  useEffect(() => {
    if (onSelectionsChange) {
      onSelectionsChange(selectedBrands, selectedTerms);
    }
  }, [selectedBrands, selectedTerms, onSelectionsChange]);


  const loadData = async () => {
    setLoading(true);
    console.log('[BrandsTermsManager] Loading data for vertical:', selectedVertical);
    try {
      const [brandsResponse, termsResponse] = await Promise.all([
        apiService.getBrands(selectedVertical),
        apiService.getTerms(selectedVertical)
      ]);
      console.log('[BrandsTermsManager] Loaded brands for', selectedVertical, ':', brandsResponse.brands?.length || 0);
      console.log('[BrandsTermsManager] Loaded terms for', selectedVertical, ':', termsResponse.terms?.length || 0);
      
      // Handle enhanced terms structure with phonetic data
      const termsData = termsResponse.terms || [];
      if (Array.isArray(termsData) && termsData.length > 0 && typeof termsData[0] === 'object') {
        // Enhanced structure with phonetic data
        const termNames = termsData.map((t: any) => t.name);
        const termMetadata = termsData.reduce((acc: any, t: any) => {
          acc[t.name] = { phonetic: t.pronunciation || '', difficulty: t.difficulty || 'intermediate' };
          return acc;
        }, {});
        setAvailableTerms(termNames);
        setEnhancedTerms(termMetadata);
      } else {
        // Fallback to simple string array
        setAvailableTerms(termsData);
      }
      
      // Handle enhanced brands structure with phonetic data
      const brandsData = brandsResponse.brands || [];
      if (Array.isArray(brandsData) && brandsData.length > 0 && typeof brandsData[0] === 'object') {
        // Enhanced structure with phonetic data
        const brandNames = brandsData.map((b: any) => b.name);
        const brandMetadata = brandsData.reduce((acc: any, b: any) => {
          acc[b.name] = { phonetic: b.pronunciation || '', difficulty: b.difficulty || 'intermediate' };
          return acc;
        }, {});
        setAvailableBrands(brandNames);
        setEnhancedBrands(brandMetadata);
      } else {
        // Fallback to simple string array
        setAvailableBrands(brandsData);
      }
    } catch (error) {
      console.error('[BrandsTermsManager] Failed to load brands/terms:', error);
      // Set empty arrays on error to prevent crashes
      setAvailableBrands([]);
      setAvailableTerms([]);
    } finally {
      setLoading(false);
      console.log('[BrandsTermsManager] Loading complete');
    }
  };

  const handleAddBrand = async () => {
    if (!newBrand.trim()) return;
    
    try {
      // Get form values from the UI
      const pronunciationInput = document.getElementById('brand-pronunciation') as HTMLInputElement;
      const difficultySelect = document.querySelector('.brand-difficulty-select') as HTMLSelectElement;
      
      const pronunciation = pronunciationInput?.value || '';
      const difficulty = difficultySelect?.value || 'intermediate';
      
      await apiService.addBrand(newBrand.trim(), selectedVertical, pronunciation, difficulty);
      setAvailableBrands([...availableBrands, newBrand.trim()]);
      
      // Store enhanced brand data locally
      if (pronunciation.trim()) {
        setEnhancedBrands(prev => ({
          ...prev,
          [newBrand.trim()]: {
            phonetic: pronunciation.trim(),
            difficulty: difficulty
          }
        }));
      }
      
      setNewBrand('');
      if (pronunciationInput) pronunciationInput.value = '';
      if (difficultySelect) difficultySelect.value = 'intermediate';
    } catch (error) {
      console.error('Failed to add brand:', error);
    }
  };


  const handleAddTerm = async () => {
    if (!newTerm.trim()) return;
    if (newTermDifficulty === 'hard' && !newTermPronunciation.trim()) {
      alert('Please provide a pronunciation guide for hard terms');
      return;
    }
    
    try {
      await apiService.addTerm(newTerm.trim(), selectedVertical, newTermPronunciation.trim(), newTermDifficulty);
      setAvailableTerms([...availableTerms, newTerm.trim()]);
      
      // Store enhanced term data locally for immediate UI display
      if (newTermPronunciation.trim()) {
        setEnhancedTerms(prev => ({
          ...prev,
          [newTerm.trim()]: {
            phonetic: newTermPronunciation.trim(),
            difficulty: newTermDifficulty
          }
        }));
      }
      setNewTerm('');
      setNewTermPronunciation('');
      setNewTermDifficulty('intermediate');
    } catch (error) {
      console.error('Failed to add term:', error);
    }
  };



  const handleToggleBrand = (brand: string) => {
    if (operationLoading) return;
    
    const isSelected = selectedBrands.includes(brand);
    if (isSelected) {
      setSelectedBrands(selectedBrands.filter(b => b !== brand));
    } else {
      setSelectedBrands([...selectedBrands, brand]);
    }
  };

  const handleToggleTerm = (term: string) => {
    if (operationLoading) return;
    
    const isSelected = selectedTerms.includes(term);
    if (isSelected) {
      setSelectedTerms(selectedTerms.filter(t => t !== term));
    } else {
      setSelectedTerms([...selectedTerms, term]);
    }
  };

  // Selection management functions
  const handleSelectAllBrands = () => {
    setSelectedBrands([...availableBrands]);
  };

  const handleDeselectAllBrands = () => {
    setSelectedBrands([]);
  };

  const handleSelectRemainingBrands = () => {
    const remaining = availableBrands.filter(brand => !selectedBrands.includes(brand));
    setSelectedBrands([...selectedBrands, ...remaining]);
  };

  const handleSelectAllTerms = () => {
    setSelectedTerms([...availableTerms]);
  };

  const handleDeselectAllTerms = () => {
    setSelectedTerms([]);
  };

  const handleSelectRemainingTerms = () => {
    const remaining = availableTerms.filter(term => !selectedTerms.includes(term));
    setSelectedTerms([...selectedTerms, ...remaining]);
  };

  // Single checkbox state helpers
  const getBrandSelectionState = () => {
    if (selectedBrands.length === 0) return 'none';
    if (selectedBrands.length === availableBrands.length) return 'all';
    return 'partial';
  };

  const getTermSelectionState = () => {
    if (selectedTerms.length === 0) return 'none';
    if (selectedTerms.length === availableTerms.length) return 'all';
    return 'partial';
  };

  // Single checkbox handlers
  const handleBrandSelectionAction = () => {
    const state = getBrandSelectionState();
    switch (state) {
      case 'none':
        handleSelectAllBrands();
        break;
      case 'partial':
        handleSelectRemainingBrands();
        break;
      case 'all':
        handleDeselectAllBrands();
        break;
    }
  };

  const handleTermSelectionAction = () => {
    const state = getTermSelectionState();
    switch (state) {
      case 'none':
        handleSelectAllTerms();
        break;
      case 'partial':
        handleSelectRemainingTerms();
        break;
      case 'all':
        handleDeselectAllTerms();
        break;
    }
  };

  // Difficulty level selection helpers
  // Difficulty-based selection handlers
  const handleSelectDifficultyBrands = (difficulty: 'easy' | 'intermediate' | 'hard') => {
    const difficultyBrands = availableBrands.filter(brand => {
      const brandDifficulty = enhancedBrands[brand]?.difficulty || 'intermediate';
      return brandDifficulty === difficulty;
    });
    const allSelected = difficultyBrands.every(brand => selectedBrands.includes(brand));
    
    if (allSelected) {
      // Deselect all brands of this difficulty
      setSelectedBrands(prev => prev.filter(brand => !difficultyBrands.includes(brand)));
    } else {
      // Select all brands of this difficulty
      const newSelected = [...selectedBrands];
      difficultyBrands.forEach(brand => {
        if (!newSelected.includes(brand)) {
          newSelected.push(brand);
        }
      });
      setSelectedBrands(newSelected);
    }
  };

  const handleSelectDifficultyTerms = (difficulty: 'easy' | 'intermediate' | 'hard') => {
    const difficultyTerms = availableTerms.filter(term => {
      const termDifficulty = enhancedTerms[term]?.difficulty || 'intermediate';
      return termDifficulty === difficulty;
    });
    const allSelected = difficultyTerms.every(term => selectedTerms.includes(term));
    
    if (allSelected) {
      // Deselect all terms of this difficulty
      setSelectedTerms(prev => prev.filter(term => !difficultyTerms.includes(term)));
    } else {
      // Select all terms of this difficulty
      const newSelected = [...selectedTerms];
      difficultyTerms.forEach(term => {
        if (!newSelected.includes(term)) {
          newSelected.push(term);
        }
      });
      setSelectedTerms(newSelected);
    }
  };

  // Check if all items of a difficulty are selected
  const isDifficultyFullySelected = (items: string[], difficulty: 'easy' | 'intermediate' | 'hard', enhancedData: {[key: string]: {phonetic: string, difficulty: string}}, selectedItems: string[]) => {
    const difficultyItems = items.filter(item => {
      const itemDifficulty = enhancedData[item]?.difficulty || 'intermediate';
      return itemDifficulty === difficulty;
    });
    return difficultyItems.length > 0 && difficultyItems.every(item => selectedItems.includes(item));
  };

  // Utility functions for collapsible sections and grouping
  const toggleSection = (difficulty: 'easy' | 'intermediate' | 'hard') => {
    setCollapsedSections(prev => ({
      ...prev,
      [difficulty]: !prev[difficulty]
    }));
  };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return 'green';
      case 'intermediate': return 'blue'; 
      case 'hard': return 'orange';
      default: return 'gray';
    }
  };

  const getDifficultyColorClasses = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return {
        bg: 'bg-green-50',
        border: 'border-green-300',
        text: 'text-green-600',
        ring: 'focus:ring-green-500'
      };
      case 'intermediate': return {
        bg: 'bg-blue-50',
        border: 'border-blue-300', 
        text: 'text-blue-600',
        ring: 'focus:ring-blue-500'
      };
      case 'hard': return {
        bg: 'bg-orange-50',
        border: 'border-orange-300',
        text: 'text-orange-600',
        ring: 'focus:ring-orange-500'
      };
      default: return {
        bg: 'bg-gray-50',
        border: 'border-gray-300',
        text: 'text-gray-600', 
        ring: 'focus:ring-gray-500'
      };
    }
  };

  const getSelectionStats = (items: string[], difficulty: 'easy' | 'intermediate' | 'hard', enhancedData: {[key: string]: {phonetic: string, difficulty: string}}, selectedItems: string[]) => {
    const difficultyItems = items.filter(item => {
      const itemDifficulty = enhancedData[item]?.difficulty || 'intermediate';
      return itemDifficulty === difficulty;
    });
    const selectedCount = difficultyItems.filter(item => selectedItems.includes(item)).length;
    return { selected: selectedCount, total: difficultyItems.length };
  };


  const handleEditBrand = (brand: string) => {
    setEditingBrand(brand);
    setEditFormData({
      name: brand,
      phonetic: enhancedBrands[brand]?.phonetic || '',
      difficulty: enhancedBrands[brand]?.difficulty || 'intermediate'
    });
  };

  const handleEditTerm = (term: string) => {
    setEditingTerm(term);
    setEditFormData({
      name: term,
      phonetic: enhancedTerms[term]?.phonetic || '',
      difficulty: enhancedTerms[term]?.difficulty || 'intermediate'
    });
  };

  const handleSaveEdit = async () => {
    if (editingBrand) {
      try {
        // Delete old brand and add new one with updated data
        await apiService.deleteBrand(editingBrand);
        await apiService.addBrand(editFormData.name, selectedVertical, editFormData.phonetic, editFormData.difficulty);
        setAvailableBrands(availableBrands.map(b => b === editingBrand ? editFormData.name : b));
        
        // Update enhanced brands data
        const newEnhancedBrands = { ...enhancedBrands };
        delete newEnhancedBrands[editingBrand];
        if (editFormData.phonetic.trim()) {
          newEnhancedBrands[editFormData.name] = {
            phonetic: editFormData.phonetic,
            difficulty: editFormData.difficulty
          };
        }
        setEnhancedBrands(newEnhancedBrands);
        setEditingBrand(null);
      } catch (error) {
        console.error('Failed to edit brand:', error);
      }
    } else if (editingTerm) {
      try {
        // Delete old term and add new one with updated data
        await apiService.deleteTerm(editingTerm);
        await apiService.addTerm(editFormData.name, selectedVertical, editFormData.phonetic, editFormData.difficulty);
        setAvailableTerms(availableTerms.map(t => t === editingTerm ? editFormData.name : t));
        
        // Update enhanced terms data
        const newEnhancedTerms = { ...enhancedTerms };
        delete newEnhancedTerms[editingTerm];
        if (editFormData.phonetic.trim()) {
          newEnhancedTerms[editFormData.name] = {
            phonetic: editFormData.phonetic,
            difficulty: editFormData.difficulty
          };
        }
        setEnhancedTerms(newEnhancedTerms);
        setEditingTerm(null);
      } catch (error) {
        console.error('Failed to edit term:', error);
      }
    }
    setEditFormData({name: '', phonetic: '', difficulty: 'intermediate'});
  };

  const handleCancelEdit = () => {
    setEditingBrand(null);
    setEditingTerm(null);
    setEditFormData({name: '', phonetic: '', difficulty: 'intermediate'});
  };

  const groupItemsByDifficulty = (items: string[], enhancedData: {[key: string]: {phonetic: string, difficulty: string}}) => {
    const grouped = {
      easy: [] as string[],
      intermediate: [] as string[],
      hard: [] as string[]
    };
    
    items.forEach(item => {
      const difficulty = enhancedData[item]?.difficulty || 'intermediate';
      if (difficulty in grouped) {
        grouped[difficulty as keyof typeof grouped].push(item);
      } else {
        grouped.intermediate.push(item);
      }
    });
    
    return grouped;
  };

  const renderDifficultySection = (
    title: string,
    items: string[],
    enhancedData: {[key: string]: {phonetic: string, difficulty: string}},
    type: 'brands' | 'terms',
    difficulty: 'easy' | 'intermediate' | 'hard'
  ) => {
    if (items.length === 0) return null;
    
    const difficultyColors = {
      easy: 'text-green-600 bg-green-50 border-green-200',
      intermediate: 'text-blue-600 bg-blue-50 border-blue-200', 
      hard: 'text-orange-600 bg-orange-50 border-orange-200'
    };
    
    const difficultyColorClasses = getDifficultyColorClasses(difficulty);
    const forDeletion = type === 'brands' ? brandsForDeletion : termsForDeletion;
    const setForDeletion = type === 'brands' ? setBrandsForDeletion : setTermsForDeletion;
    const handleToggle = type === 'brands' ? handleToggleBrand : handleToggleTerm;
    const handleEdit = type === 'brands' ? handleEditBrand : handleEditTerm;
    const editingItem = type === 'brands' ? editingBrand : editingTerm;
    const selectedItems = type === 'brands' ? selectedBrands : selectedTerms;
    
    const isFullySelected = isDifficultyFullySelected(type === 'brands' ? availableBrands : availableTerms, difficulty, enhancedData, selectedItems);
    const hasSomeSelected = items.some(item => selectedItems.includes(item));
    
    return (
      <div className="mb-4">
        <div 
          className={`flex items-center justify-between p-2 rounded-lg border ${difficultyColors[difficulty]} cursor-pointer hover:bg-opacity-75`}
          onClick={() => toggleSection(difficulty)}
        >
          <div className="flex items-center space-x-3">
            <button
              className="flex items-center justify-center w-6 h-6 text-gray-600 hover:text-gray-800 transition-transform duration-200"
              onClick={(e) => {
                e.stopPropagation();
                toggleSection(difficulty);
              }}
            >
              <svg 
                className={`w-4 h-4 transition-transform duration-200 ${collapsedSections[difficulty] ? 'rotate-0' : 'rotate-90'}`}
                fill="currentColor" 
                viewBox="0 0 20 20"
              >
                <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            </button>
            {!deleteMode && (
              <label className="flex items-center cursor-pointer" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={isFullySelected}
                  ref={(input) => {
                    if (input) input.indeterminate = hasSomeSelected && !isFullySelected;
                  }}
                  onChange={() => {
                    if (type === 'brands') {
                      handleSelectDifficultyBrands(difficulty);
                    } else {
                      handleSelectDifficultyTerms(difficulty);
                    }
                  }}
                  className={`w-4 h-4 ${difficultyColorClasses.text.replace('text-', 'text-')} bg-gray-100 border-gray-300 rounded ${difficultyColorClasses.ring} focus:ring-2`}
                />
              </label>
            )}
            <h4 className="text-sm font-semibold">
              {(() => {
                const selectedCount = items.filter(item => selectedItems.includes(item)).length;
                return `${selectedCount}/${items.length} selected`;
              })()}
            </h4>
          </div>
          <span className="text-xs font-medium px-2 py-1 rounded-full bg-white border">
            {difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}
          </span>
        </div>
        {!collapsedSections[difficulty] && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
          {items.map((item, index) => {
            const isSelected = selectedItems.includes(item);
            return (
              <div
                key={`${difficulty}-${index}`}
                className={`flex items-center p-3 rounded-md transition-colors border-2 ${
                  deleteMode 
                    ? (forDeletion.has(item) ? 'bg-red-100 border-red-300' : 'bg-white border-gray-200')
                    : (isSelected ? `${difficultyColorClasses.bg} ${difficultyColorClasses.border} shadow-sm` : 'bg-gray-50 border-gray-200 hover:bg-gray-100')
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  {/* Normal mode: checkbox for immediate add/remove */}
                  {!deleteMode && (
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggle(item)}
                        disabled={operationLoading}
                        className={`w-4 h-4 ${difficultyColorClasses.text} bg-gray-100 border-gray-300 rounded ${difficultyColorClasses.ring} focus:ring-2 disabled:opacity-50`}
                      />
                    </label>
                  )}
                  
                  {/* Delete mode: show delete checkbox */}
                  {deleteMode && (
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={forDeletion.has(item)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setForDeletion(prev => new Set(prev).add(item));
                          } else {
                            setForDeletion(prev => {
                              const newSet = new Set(prev);
                              newSet.delete(item);
                              return newSet;
                            });
                          }
                        }}
                        className="w-4 h-4 text-red-600 bg-gray-100 border-gray-300 rounded focus:ring-red-500 focus:ring-2"
                      />
                    </label>
                  )}
                  
                  {/* Item Name with Edit functionality */}
                  {editingItem === item ? (
                    <div className="flex-1 ml-2 space-y-2">
                      <div className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={editFormData.name}
                          onChange={(e) => setEditFormData({...editFormData, name: e.target.value})}
                          className={`flex-1 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 ${difficultyColorClasses.ring}`}
                          placeholder={`${type.slice(0, -1)} name`}
                        />
                        <button
                          onClick={handleSaveEdit}
                          disabled={!editFormData.name?.trim()}
                          className="px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50"
                        >
                          ✓
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="px-2 py-1 bg-gray-600 text-white rounded text-xs hover:bg-gray-700"
                        >
                          ✕
                        </button>
                      </div>
                      <div className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={editFormData.phonetic}
                          onChange={(e) => setEditFormData({...editFormData, phonetic: e.target.value})}
                          className={`flex-1 px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-2 ${difficultyColorClasses.ring}`}
                          placeholder="Pronunciation guide (e.g., BOH-tox)"
                        />
                        <select
                          value={editFormData.difficulty}
                          onChange={(e) => setEditFormData({...editFormData, difficulty: e.target.value})}
                          className={`px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-2 ${difficultyColorClasses.ring}`}
                        >
                          <option value="easy">Easy</option>
                          <option value="intermediate">Intermediate</option>
                          <option value="hard">Hard</option>
                        </select>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 ml-2 flex items-center justify-between">
                      <div>
                        <span className="text-sm font-medium block">
                          {item}
                        </span>
                        {isSelected && enhancedData[item] && (
                          <div className="text-xs text-gray-500 italic mt-1">
                            {enhancedData[item].phonetic && (
                              <div className="block text-gray-600">
                                {enhancedData[item].phonetic}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                      {isSelected && !deleteMode && (
                        <button
                          onClick={() => handleEdit(item)}
                          className={`ml-2 px-2 py-1 ${difficultyColorClasses.bg} ${difficultyColorClasses.text} rounded text-xs hover:bg-opacity-75 transition-colors`}
                        >
                          Edit
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          </div>
        )}
      </div>
    );
  };


  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-4xl max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            Manage Brands & Terms
            {operationLoading && (
              <div className="inline-flex items-center ml-3">
                <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
                <span className="ml-2 text-sm text-blue-600">Processing...</span>
              </div>
            )}
          </h2>
          <button
            onClick={onClose}
            disabled={operationLoading}
            className={`${
              operationLoading
                ? 'text-gray-300 cursor-not-allowed'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            <span className="sr-only">Close</span>
            ✕
          </button>
        </div>

        {/* Vertical Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Medical Vertical (affects preloaded options)
          </label>
          <select
            value={selectedVertical}
            onChange={(e) => setSelectedVertical(e.target.value as 'aesthetic_medicine' | 'dermatology' | 'plastic_surgery' | 'venous_care')}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="aesthetic_medicine">Aesthetic Medicine</option>
            <option value="dermatology">Dermatology</option>
            <option value="plastic_surgery">Plastic Surgery</option>
            <option value="venous_care">Venous Care</option>
          </select>
        </div>

        <div className="mb-6">
          <div className="flex space-x-1">
            <button
              onClick={() => setActiveTab('brands')}
              className={`px-4 py-2 rounded-md text-sm font-medium ${
                activeTab === 'brands'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Brand Names ({availableBrands.length})
            </button>
            <button
              onClick={() => setActiveTab('terms')}
              className={`px-4 py-2 rounded-md text-sm font-medium ${
                activeTab === 'terms'
                  ? 'bg-green-100 text-green-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Medical Terms ({availableTerms.length})
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-8">
            <div className="spinner"></div>
          </div>
        ) : (
          <>
            {console.log('[BrandsTermsManager] Rendering content - activeTab:', activeTab, 'brands length:', availableBrands.length, 'loading:', loading)}
            {activeTab === 'brands' && (
              <div>
                <div className="mb-4 space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Brand Name
                    </label>
                    <input
                      type="text"
                      value={newBrand}
                      onChange={(e) => setNewBrand(e.target.value)}
                      placeholder="Enter new brand name"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      onKeyPress={(e) => e.key === 'Enter' && document.getElementById('brand-pronunciation')?.focus()}
                    />
                  </div>
                  <div>
                    <label htmlFor="brand-pronunciation" className="block text-sm font-medium text-gray-700 mb-1">
                      Pronunciation Guide (Required)
                    </label>
                    <input
                      id="brand-pronunciation"
                      type="text"
                      placeholder="e.g., JUH-veh-derm or BOH-tox"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Pronunciation Difficulty
                    </label>
                    <select className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 brand-difficulty-select" defaultValue="intermediate">
                      <option value="easy">Easy - Well-known brands</option>
                      <option value="intermediate">Intermediate - Moderate complexity</option>
                      <option value="hard">Hard - Requires pronunciation guide</option>
                    </select>
                  </div>
                  <div className="flex justify-end">
                    <button
                      onClick={handleAddBrand}
                      disabled={!newBrand.trim()}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Add New Brand
                    </button>
                  </div>
                </div>


                {/* Available Brands */}
                <div className="mb-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-3">
                    <h3 className="text-lg font-medium text-gray-900 mb-2 sm:mb-0">
                      Available {selectedVertical === 'aesthetic_medicine' ? 'Aesthetic Medicine' : 
                        selectedVertical === 'dermatology' ? 'Dermatology' :
                        selectedVertical === 'plastic_surgery' ? 'Plastic Surgery' :
                        selectedVertical === 'venous_care' ? 'Venous Care' : selectedVertical} Brands
                    </h3>
                    <div className="flex items-center space-x-4">
                      {/* Selection controls - always visible */}
                      {!deleteMode && (
                        <div className="flex items-center space-x-4">
                          <label className="flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={getBrandSelectionState() === 'all'}
                              ref={(input) => {
                                if (input) input.indeterminate = getBrandSelectionState() === 'partial';
                              }}
                              onChange={handleBrandSelectionAction}
                              className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                            />
                            <span className="ml-2 text-sm font-medium text-gray-700">
                              {(() => {
                                const state = getBrandSelectionState();
                                const totalCount = availableBrands.length;
                                const selectedCount = selectedBrands.length;
                                const remainingCount = totalCount - selectedCount;
                                
                                if (state === 'none') {
                                  return `Select All (${totalCount})`;
                                } else if (state === 'all') {
                                  return `Deselect All (${selectedCount})`;
                                } else {
                                  return `Select Remaining (${remainingCount})`;
                                }
                              })()}
                            </span>
                          </label>
                        </div>
                      )}
                      
                      <button
                        onClick={() => {
                          setDeleteMode(!deleteMode);
                          setBrandsForDeletion(new Set());
                        }}
                        className={`px-3 py-1 text-sm rounded-md transition-colors ${
                          deleteMode
                            ? 'bg-red-100 text-red-700 hover:bg-red-200'
                            : 'bg-red-600 text-white hover:bg-red-700'
                        }`}
                      >
                        {deleteMode ? 'Exit Delete Mode' : 'Delete Brands'}
                      </button>
                      {deleteMode && brandsForDeletion.size > 0 && (
                        <button
                          onClick={() => {
                            setDeleteType('brands');
                            setShowDeleteConfirmation(true);
                          }}
                          className="px-3 py-1 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                        >
                          Delete Selected ({brandsForDeletion.size})
                        </button>
                      )}
                      {deleteMode && (
                        <label className="flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={brandsForDeletion.size > 0}
                            ref={(el) => {
                              if (el) {
                                const selectedCount = brandsForDeletion.size;
                                el.indeterminate = selectedCount > 0 && selectedCount < availableBrands.length;
                              }
                            }}
                            onChange={() => {
                              const selectedCount = brandsForDeletion.size;
                              const totalCount = availableBrands.length;
                              
                              if (selectedCount === 0) {
                                // Select All
                                setBrandsForDeletion(new Set(availableBrands));
                              } else if (selectedCount === totalCount) {
                                // Deselect All
                                setBrandsForDeletion(new Set());
                              } else {
                                // Select Remaining
                                const remaining = availableBrands.filter(brand => !brandsForDeletion.has(brand));
                                const newSet = new Set(brandsForDeletion);
                                remaining.forEach(brand => newSet.add(brand));
                                setBrandsForDeletion(newSet);
                              }
                            }}
                            disabled={operationLoading}
                            className="w-5 h-5 text-red-600 bg-gray-100 border-2 border-gray-400 rounded focus:ring-red-500 focus:ring-2 mr-2 disabled:opacity-50"
                          />
                          <span className="text-sm text-gray-600 font-medium">
                            {(() => {
                              const selectedCount = brandsForDeletion.size;
                              const totalCount = availableBrands.length;
                              
                              if (selectedCount === 0) {
                                return `Select All (${totalCount})`;
                              } else if (selectedCount === totalCount) {
                                return `Deselect All (${selectedCount})`;
                              } else {
                                const remainingCount = totalCount - selectedCount;
                                return `Select Remaining (${remainingCount})`;
                              }
                            })()}
                          </span>
                        </label>
                      )}
                    </div>
                  </div>
                  {/* Difficulty-based brand sections */}
                  <div className="space-y-4">
                    {(() => {
                      const groupedBrands = groupItemsByDifficulty(availableBrands, enhancedBrands);
                      return (
                        <>
                          {renderDifficultySection('Easy Brands', groupedBrands.easy, enhancedBrands, 'brands', 'easy')}
                          {renderDifficultySection('Intermediate Brands', groupedBrands.intermediate, enhancedBrands, 'brands', 'intermediate')}
                          {renderDifficultySection('Hard Brands', groupedBrands.hard, enhancedBrands, 'brands', 'hard')}
                        </>
                      );
                    })()}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'terms' && (
              <div>
                <div className="mb-4 space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Medical Term Name
                    </label>
                    <input
                      type="text"
                      value={newTerm}
                      onChange={(e) => setNewTerm(e.target.value)}
                      placeholder="Enter new medical term"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                      onKeyPress={(e) => e.key === 'Enter' && document.getElementById('pronunciation-input')?.focus()}
                    />
                  </div>
                  <div>
                    <label htmlFor="pronunciation-input" className="block text-sm font-medium text-gray-700 mb-1">
                      Pronunciation Guide (Required)
                    </label>
                    <input
                      id="pronunciation-input"
                      type="text"
                      value={newTermPronunciation}
                      onChange={(e) => setNewTermPronunciation(e.target.value)}
                      placeholder="e.g., men-toe-LAY-bee-al fold or bye-oh-STIM-you-lay-shun"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                      onKeyPress={(e) => e.key === 'Enter' && handleAddTerm()}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Pronunciation Difficulty
                    </label>
                    <select
                      value={newTermDifficulty}
                      onChange={(e) => setNewTermDifficulty(e.target.value as 'easy' | 'intermediate' | 'hard')}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                    >
                      <option value="easy">Easy - Common terms</option>
                      <option value="intermediate">Intermediate - Moderate complexity</option>
                      <option value="hard">Hard - Requires pronunciation guide</option>
                    </select>
                  </div>
                  <div className="flex justify-end">
                    <button
                      onClick={handleAddTerm}
                      disabled={!newTerm.trim() || (newTermDifficulty === 'hard' && !newTermPronunciation.trim())}
                      className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Add New Term
                    </button>
                  </div>
                </div>


                {/* Available Terms */}
                <div className="mb-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-3">
                    <h3 className="text-lg font-medium text-gray-900 mb-2 sm:mb-0">
                      Available {selectedVertical === 'aesthetic_medicine' ? 'Aesthetic Medicine' : 
                        selectedVertical === 'dermatology' ? 'Dermatology' :
                        selectedVertical === 'plastic_surgery' ? 'Plastic Surgery' :
                        selectedVertical === 'venous_care' ? 'Venous Care' : selectedVertical} Terms
                    </h3>
                    <div className="flex items-center space-x-4">
                      {/* Selection controls - always visible */}
                      {!deleteMode && (
                        <div className="flex items-center space-x-4">
                          <label className="flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={getTermSelectionState() === 'all'}
                              ref={(input) => {
                                if (input) input.indeterminate = getTermSelectionState() === 'partial';
                              }}
                              onChange={handleTermSelectionAction}
                              className="w-4 h-4 text-green-600 bg-gray-100 border-gray-300 rounded focus:ring-green-500 focus:ring-2"
                            />
                            <span className="ml-2 text-sm font-medium text-gray-700">
                              {(() => {
                                const state = getTermSelectionState();
                                const totalCount = availableTerms.length;
                                const selectedCount = selectedTerms.length;
                                const remainingCount = totalCount - selectedCount;
                                
                                if (state === 'none') {
                                  return `Select All (${totalCount})`;
                                } else if (state === 'all') {
                                  return `Deselect All (${selectedCount})`;
                                } else {
                                  return `Select Remaining (${remainingCount})`;
                                }
                              })()}
                            </span>
                          </label>
                        </div>
                      )}
                      
                      <button
                        onClick={() => {
                          setDeleteMode(!deleteMode);
                          setTermsForDeletion(new Set());
                        }}
                        className={`px-3 py-1 text-sm rounded-md transition-colors ${
                          deleteMode
                            ? 'bg-red-100 text-red-700 hover:bg-red-200'
                            : 'bg-red-600 text-white hover:bg-red-700'
                        }`}
                      >
                        {deleteMode ? 'Exit Delete Mode' : 'Delete Terms'}
                      </button>
                      {deleteMode && termsForDeletion.size > 0 && (
                        <button
                          onClick={() => {
                            setDeleteType('terms');
                            setShowDeleteConfirmation(true);
                          }}
                          className="px-3 py-1 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                        >
                          Delete Selected ({termsForDeletion.size})
                        </button>
                      )}
                      {deleteMode && (
                        <label className="flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={termsForDeletion.size > 0}
                            ref={(el) => {
                              if (el) {
                                const selectedCount = termsForDeletion.size;
                                el.indeterminate = selectedCount > 0 && selectedCount < availableTerms.length;
                              }
                            }}
                            onChange={() => {
                              const selectedCount = termsForDeletion.size;
                              const totalCount = availableTerms.length;
                              
                              if (selectedCount === 0) {
                                // Select All
                                setTermsForDeletion(new Set(availableTerms));
                              } else if (selectedCount === totalCount) {
                                // Deselect All
                                setTermsForDeletion(new Set());
                              } else {
                                // Select Remaining
                                const remaining = availableTerms.filter(term => !termsForDeletion.has(term));
                                const newSet = new Set(termsForDeletion);
                                remaining.forEach(term => newSet.add(term));
                                setTermsForDeletion(newSet);
                              }
                            }}
                            disabled={operationLoading}
                            className="w-5 h-5 text-red-600 bg-gray-100 border-2 border-gray-400 rounded focus:ring-red-500 focus:ring-2 mr-2 disabled:opacity-50"
                          />
                          <span className="text-sm text-gray-600 font-medium">
                            {(() => {
                              const selectedCount = termsForDeletion.size;
                              const totalCount = availableTerms.length;
                              
                              if (selectedCount === 0) {
                                return `Select All (${totalCount})`;
                              } else if (selectedCount === totalCount) {
                                return `Deselect All (${selectedCount})`;
                              } else {
                                const remainingCount = totalCount - selectedCount;
                                return `Select Remaining (${remainingCount})`;
                              }
                            })()}
                          </span>
                        </label>
                      )}
                    </div>
                  </div>
                  {/* Difficulty-based terms sections */}
                  <div className="space-y-4">
                    {(() => {
                      const groupedTerms = groupItemsByDifficulty(availableTerms, enhancedTerms);
                      return (
                        <>
                          {renderDifficultySection('Easy Terms', groupedTerms.easy, enhancedTerms, 'terms', 'easy')}
                          {renderDifficultySection('Intermediate Terms', groupedTerms.intermediate, enhancedTerms, 'terms', 'intermediate')}
                          {renderDifficultySection('Hard Terms', groupedTerms.hard, enhancedTerms, 'terms', 'hard')}
                        </>
                      );
                    })()}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            disabled={operationLoading}
            className={`px-4 py-2 rounded-md ${
              operationLoading
                ? 'bg-gray-400 text-gray-200 cursor-not-allowed'
                : 'bg-gray-600 text-white hover:bg-gray-700'
            }`}
          >
            {operationLoading ? (
              <div className="flex items-center">
                <div className="animate-spin h-4 w-4 border-2 border-gray-200 border-t-transparent rounded-full mr-2"></div>
                Processing...
              </div>
            ) : (
              'Close'
            )}
          </button>
        </div>
      </div>
      
      {/* Delete Confirmation Modal */}
      {showDeleteConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-gray-900">
                  Delete {deleteType === 'brands' ? 'Brands' : 'Terms'}?
                </h3>
              </div>
            </div>
            
            <div className="mb-6">
              <p className="text-sm text-gray-600">
                Are you sure you want to permanently delete the selected {deleteType === 'brands' ? 'brands' : 'terms'}? 
                <span className="font-semibold text-red-600"> This action cannot be undone and will affect all users.</span>
              </p>
              <div className="mt-3 p-3 bg-red-50 rounded-lg">
                <p className="text-sm text-red-800">
                  Selected for deletion: <span className="font-medium">
                    {(() => {
                      if (deleteType === 'brands') {
                        const actuallyAddedCount = Array.from(brandsForDeletion).filter(brand => availableBrands.includes(brand)).length;
                        const totalSelected = brandsForDeletion.size;
                        return `${actuallyAddedCount} added brands (${totalSelected} total selected)`;
                      } else {
                        const actuallyAddedCount = Array.from(termsForDeletion).filter(term => availableTerms.includes(term)).length;
                        const totalSelected = termsForDeletion.size;
                        return `${actuallyAddedCount} added terms (${totalSelected} total selected)`;
                      }
                    })()}
                  </span>
                </p>
                {(() => {
                  const notAddedCount = deleteType === 'brands' 
                    ? Array.from(brandsForDeletion).filter(brand => !availableBrands.includes(brand)).length
                    : Array.from(termsForDeletion).filter(term => !availableTerms.includes(term)).length;
                  
                  if (notAddedCount > 0) {
                    return (
                      <p className="text-xs text-gray-600 mt-1">
                        Note: {notAddedCount} selected {deleteType === 'brands' ? 'brands' : 'terms'} are not added and will be ignored.
                      </p>
                    );
                  }
                  return null;
                })()}
              </div>
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowDeleteConfirmation(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (deleteType === 'brands') {
                    const brandsToDelete = Array.from(brandsForDeletion);
                    if (brandsToDelete.length > 0) {
                      const deletePromises = brandsToDelete.map(brand => apiService.deleteBrand(brand));
                      await Promise.all(deletePromises);
                      setAvailableBrands(availableBrands.filter(brand => !brandsForDeletion.has(brand)));
                      // Also remove from selected if they were selected
                      setSelectedBrands(selectedBrands.filter(brand => !brandsForDeletion.has(brand)));
                      
                      // Clear enhanced brands data for deleted items
                      const newEnhancedBrands = { ...enhancedBrands };
                      brandsToDelete.forEach(brand => delete newEnhancedBrands[brand]);
                      setEnhancedBrands(newEnhancedBrands);
                    }
                    setBrandsForDeletion(new Set());
                  } else {
                    const termsToDelete = Array.from(termsForDeletion);
                    if (termsToDelete.length > 0) {
                      const deletePromises = termsToDelete.map(term => apiService.deleteTerm(term));
                      await Promise.all(deletePromises);
                      setAvailableTerms(availableTerms.filter(term => !termsForDeletion.has(term)));
                      // Also remove from selected if they were selected
                      setSelectedTerms(selectedTerms.filter(term => !termsForDeletion.has(term)));
                      
                      // Clear enhanced terms data for deleted items
                      const newEnhancedTerms = { ...enhancedTerms };
                      termsToDelete.forEach(term => delete newEnhancedTerms[term]);
                      setEnhancedTerms(newEnhancedTerms);
                    }
                    setTermsForDeletion(new Set());
                  }
                  setShowDeleteConfirmation(false);
                  setDeleteMode(false);
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};