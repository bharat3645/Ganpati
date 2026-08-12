import React, { useState, useEffect } from 'react';
import { Camera, Upload, Sparkles, Download, Loader2, Heart, Star } from 'lucide-react';
import toast, { Toaster } from 'react-hot-toast';
import { apiService, Logo } from './services/api';

interface GaneshImage {
  id: string;
  name: string;
  imageUrl: string;
}

// Bundled locally (public/assets) so Step 1 works fully offline and doesn't
// depend on third-party hotlinked images staying available.
const ganeshImages: GaneshImage[] = [
  {
    id: 'ganesh_1',
    name: 'Silver Floral Ganesh',
    imageUrl: '/assets/1.jpg'
  },
  {
    id: 'ganesh_2',
    name: 'Grand Pandal Ganesh',
    imageUrl: '/assets/2.jpg'
  },
  {
    id: 'ganesh_3',
    name: 'Royal Red & Gold Ganesh',
    imageUrl: '/assets/3.jpg'
  },
  {
    id: 'ganesh_4',
    name: 'Traditional Temple Ganesh',
    imageUrl: '/assets/4.jpg'
  },
  {
    id: 'ganesh_5',
    name: 'Golden Festive Ganesh',
    imageUrl: '/assets/5.jpg'
  },
  {
    id: 'ganesh_6',
    name: 'Majestic Golden Crown Ganesh',
    imageUrl: '/assets/6.jpg'
  }
];

function App() {
  const [step, setStep] = useState(1);
  const [selectedGanesh, setSelectedGanesh] = useState<string>('');
  const [userPhoto, setUserPhoto] = useState<string>('');
  const [userPhotoBase64, setUserPhotoBase64] = useState<string>('');
  const [selectedLogo, setSelectedLogo] = useState<string>('');
  const [logos, setLogos] = useState<Logo[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState<string>('');
  const [dragActive, setDragActive] = useState(false);
  const [isLoadingLogos, setIsLoadingLogos] = useState(true);

  // Load logos from backend
  useEffect(() => {
    const loadLogos = async () => {
      try {
        setIsLoadingLogos(true);
        const fetchedLogos = await apiService.getLogos();
        setLogos(fetchedLogos);
        toast.success('Logos loaded successfully!');
      } catch (error) {
        console.error('Failed to load logos:', error);
        toast.error('Failed to load logos. Please refresh the page.');
      } finally {
        setIsLoadingLogos(false);
      }
    };

    loadLogos();
  }, []);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFile = (file: File) => {
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const result = e.target?.result as string;
        setUserPhoto(result);
        setUserPhotoBase64(result);
        toast.success('Photo uploaded successfully!');
      };
      reader.readAsDataURL(file);
    } else {
      toast.error('Please upload an image file');
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const generateImage = async () => {
    if (!selectedGanesh || !userPhotoBase64 || !selectedLogo) {
      toast.error('Please complete all steps before generating');
      return;
    }

    // Find the selected Ganesh image URL
    const selectedGaneshImage = ganeshImages.find(img => img.id === selectedGanesh);
    if (!selectedGaneshImage) {
      toast.error('Selected Ganesh image not found');
      return;
    }

    setIsGenerating(true);

    try {
      toast.loading('Creating your festive blessing...', { duration: 2000 });

      // The backend has its own bundled copy of the Ganesh backdrops and
      // loads them from local disk by id -- it never fetches a caller-
      // supplied URL for these, which closes off a whole class of SSRF risk.
      const response = await apiService.generateGreeting({
        ganeshImageId: selectedGaneshImage.id,
        userPhotoBase64: userPhotoBase64,
        selectedLogoId: selectedLogo
      });
      
      if (response.success && response.imageUrl) {
        setGeneratedImage(response.imageUrl);
        toast.success('Your festive greeting has been generated!');
      } else {
        throw new Error('Failed to generate image');
      }
    } catch (error) {
      console.error('Generation error:', error);
      toast.error('Failed to generate image. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  const resetApp = () => {
    setStep(1);
    setSelectedGanesh('');
    setUserPhoto('');
    setSelectedLogo('');
    setGeneratedImage('');
    setUserPhotoBase64('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-pink-50 to-purple-50">
      <Toaster position="top-right" />
      
      {/* Header */}
      <header className="bg-gradient-to-r from-orange-600 via-pink-600 to-purple-600 text-white py-6 shadow-lg">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-center justify-center space-x-3">
            <div className="flex items-center space-x-2">
              <Star className="w-8 h-8 text-yellow-300" />
              <h1 className="text-3xl font-bold">Festive AI Greetings</h1>
              <Heart className="w-8 h-8 text-pink-300" />
            </div>
          </div>
          <p className="text-center mt-2 text-orange-100">Create personalized Ganesh Chaturthi blessings with AI magic</p>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {!generatedImage ? (
          <>
            {/* Progress Steps */}
            <div className="flex justify-center mb-8">
              <div className="flex items-center space-x-4">
                {[1, 2, 3].map((stepNum) => (
                  <React.Fragment key={stepNum}>
                    <div className={`flex items-center justify-center w-12 h-12 rounded-full font-bold text-lg transition-all duration-300 ${
                      step >= stepNum 
                        ? 'bg-gradient-to-r from-orange-500 to-pink-500 text-white shadow-lg' 
                        : 'bg-gray-200 text-gray-500'
                    }`}>
                      {stepNum}
                    </div>
                    {stepNum < 3 && (
                      <div className={`w-16 h-1 rounded-full transition-all duration-300 ${
                        step > stepNum ? 'bg-gradient-to-r from-orange-500 to-pink-500' : 'bg-gray-200'
                      }`} />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* Step 1: Select Ganesh Background */}
            {step >= 1 && (
              <div className="bg-white rounded-2xl shadow-xl p-8 mb-8 border border-orange-100">
                <div className="flex items-center space-x-3 mb-6">
                  <div className="w-10 h-10 bg-gradient-to-r from-orange-500 to-pink-500 rounded-full flex items-center justify-center">
                    <Star className="w-5 h-5 text-white" />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800">Choose Your Sacred Ganesh Background</h2>
                </div>
                
                <div className="grid md:grid-cols-3 gap-6">
                  {ganeshImages.map((ganesh) => (
                    <div
                      key={ganesh.id}
                      onClick={() => {
                        setSelectedGanesh(ganesh.id);
                        if (step === 1) setStep(2);
                      }}
                      className={`relative cursor-pointer rounded-xl overflow-hidden transition-all duration-300 hover:scale-105 ${
                        selectedGanesh === ganesh.id 
                          ? 'ring-4 ring-orange-500 shadow-2xl' 
                          : 'shadow-lg hover:shadow-xl'
                      }`}
                    >
                      <img
                        src={ganesh.imageUrl}
                        alt={ganesh.name}
                        className="w-full h-48 object-cover"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
                      <div className="absolute bottom-4 left-4 right-4">
                        <h3 className="font-semibold text-white">{ganesh.name}</h3>
                      </div>
                      {selectedGanesh === ganesh.id && (
                        <div className="absolute top-4 right-4">
                          <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center">
                            <Sparkles className="w-4 h-4 text-white" />
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Step 2: Upload Photo */}
            {step >= 2 && (
              <div className="bg-white rounded-2xl shadow-xl p-8 mb-8 border border-orange-100">
                <div className="flex items-center space-x-3 mb-6">
                  <div className="w-10 h-10 bg-gradient-to-r from-pink-500 to-purple-500 rounded-full flex items-center justify-center">
                    <Camera className="w-5 h-5 text-white" />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800">Upload Your Photo</h2>
                </div>

                {!userPhoto ? (
                  <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-xl p-12 text-center transition-all duration-300 ${
                      dragActive 
                        ? 'border-orange-500 bg-orange-50' 
                        : 'border-gray-300 hover:border-orange-400 hover:bg-orange-50'
                    }`}
                  >
                    <Upload className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-gray-700 mb-2">Drop your photo here</h3>
                    <p className="text-gray-500 mb-6">or click to browse</p>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleFileInput}
                      className="hidden"
                      id="photo-upload"
                    />
                    <label
                      htmlFor="photo-upload"
                      className="inline-flex items-center space-x-2 bg-gradient-to-r from-orange-500 to-pink-500 text-white px-6 py-3 rounded-lg font-semibold cursor-pointer hover:from-orange-600 hover:to-pink-600 transition-all duration-300"
                    >
                      <Camera className="w-5 h-5" />
                      <span>Choose Photo</span>
                    </label>
                  </div>
                ) : (
                  <div className="flex items-center space-x-6">
                    <img
                      src={userPhoto}
                      alt="Uploaded photo"
                      className="w-32 h-32 rounded-xl object-cover shadow-lg"
                    />
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-800">Photo uploaded successfully!</h3>
                      <p className="text-gray-600">Your photo is ready to be transformed</p>
                      <button
                        onClick={() => {
                          setUserPhoto('');
                          setUserPhotoBase64('');
                        }}
                        className="mt-2 text-orange-600 hover:text-orange-700 font-medium"
                      >
                        Choose different photo
                      </button>
                    </div>
                    {userPhoto && step === 2 && (
                      <button
                        onClick={() => setStep(3)}
                        className="bg-gradient-to-r from-pink-500 to-purple-500 text-white px-6 py-3 rounded-lg font-semibold hover:from-pink-600 hover:to-purple-600 transition-all duration-300"
                      >
                        Continue
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Step 3: Select Logo */}
            {step >= 3 && (
              <div className="bg-white rounded-2xl shadow-xl p-8 mb-8 border border-orange-100">
                <div className="flex items-center space-x-3 mb-6">
                  <div className="w-10 h-10 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-white" />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800">Choose Your Organization's Logo</h2>
                </div>

                {isLoadingLogos ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                    <span className="ml-3 text-gray-600">Loading logos...</span>
                  </div>
                ) : logos.length === 0 ? (
                  <div className="text-center py-12">
                    <p className="text-gray-500">No logos available. Please check your backend connection.</p>
                  </div>
                ) : (
                  <div className="grid md:grid-cols-3 gap-6">
                    {logos.map((logo) => (
                      <div
                        key={logo.id}
                        onClick={() => setSelectedLogo(logo.id)}
                        className={`relative cursor-pointer rounded-xl overflow-hidden transition-all duration-300 hover:scale-105 ${
                          selectedLogo === logo.id 
                            ? 'ring-4 ring-purple-500 shadow-2xl' 
                            : 'shadow-lg hover:shadow-xl'
                        }`}
                      >
                        <img
                          src={logo.imageUrl}
                          alt={logo.name}
                          className="w-full h-32 object-cover bg-gray-100"
                          onError={(e) => {
                            const target = e.target as HTMLImageElement;
                            target.src = 'https://images.pexels.com/photos/7688136/pexels-photo-7688136.jpeg?auto=compress&cs=tinysrgb&w=200';
                          }}
                        />
                        <div className="p-4 bg-white">
                          <h3 className="font-semibold text-gray-800">{logo.name}</h3>
                        </div>
                        {selectedLogo === logo.id && (
                          <div className="absolute top-2 right-2">
                            <div className="w-6 h-6 bg-purple-500 rounded-full flex items-center justify-center">
                              <Sparkles className="w-3 h-3 text-white" />
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Generate Button */}
            {selectedGanesh && userPhoto && selectedLogo && !isLoadingLogos && (
              <div className="text-center">
                <button
                  onClick={generateImage}
                  disabled={isGenerating}
                  className="inline-flex items-center space-x-3 bg-gradient-to-r from-orange-600 via-pink-600 to-purple-600 text-white px-12 py-4 rounded-2xl font-bold text-lg shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="w-6 h-6 animate-spin" />
                      <span>Creating Your Blessing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-6 h-6" />
                      <span>Generate Festive Greeting</span>
                      <Star className="w-6 h-6" />
                    </>
                  )}
                </button>
              </div>
            )}
          </>
        ) : (
          /* Generated Result */
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
            <div className="flex items-center justify-center space-x-3 mb-6">
              <Star className="w-8 h-8 text-yellow-500" />
              <h2 className="text-3xl font-bold text-gray-800">Your Festive Blessing is Ready!</h2>
              <Heart className="w-8 h-8 text-pink-500" />
            </div>
            
            <div className="max-w-2xl mx-auto mb-8">
              <img
                src={generatedImage}
                alt="Generated festive greeting"
                className="w-full rounded-2xl shadow-2xl"
              />
            </div>

            <div className="flex justify-center space-x-4">
              <button
                onClick={() => {
                  const link = document.createElement('a');
                  link.href = generatedImage;
                  link.download = 'festive-greeting.jpg';
                  link.click();
                }}
                className="inline-flex items-center space-x-2 bg-gradient-to-r from-green-500 to-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:from-green-600 hover:to-green-700 transition-all duration-300"
              >
                <Download className="w-5 h-5" />
                <span>Download</span>
              </button>
              
              <button
                onClick={resetApp}
                className="inline-flex items-center space-x-2 bg-gradient-to-r from-orange-500 to-pink-500 text-white px-6 py-3 rounded-lg font-semibold hover:from-orange-600 hover:to-pink-600 transition-all duration-300"
              >
                <Sparkles className="w-5 h-5" />
                <span>Create Another</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="bg-gradient-to-r from-orange-900 to-purple-900 text-white py-8 mt-16">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <p className="text-orange-200">May Lord Ganesh bless you with happiness, prosperity, and success</p>
          <p className="text-sm text-orange-300 mt-2">🙏 Ganesh Chaturthi Celebrations 2025 🙏</p>
        </div>
      </footer>
    </div>
  );
}

export default App;